#[cfg(not(windows))]
compile_error!("the conpty extension module wraps the Win32 ConPTY API and only builds on Windows");

use std::{
    collections::VecDeque,
    io::{ErrorKind, Read, Write},
    process::Command,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Condvar, Mutex,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

use conpty_rs::{io::PipeWriter, Process, ProcessOptions};
use pyo3::{exceptions::PyRuntimeError, prelude::*, types::PyBytes};

const DEFAULT_BUFFER_SIZE: usize = 16 * 1024;
const READ_CHUNK_SIZE: usize = 8 * 1024;
const POLL_INTERVAL: Duration = Duration::from_millis(1);

fn err<E: std::fmt::Display>(e: E) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

struct State {
    buf: VecDeque<u8>,
    closed: bool,
    error: Option<String>,
}

struct Shared {
    state: Mutex<State>,
    ready: Condvar,
    drained: Condvar,
    capacity: usize,
    stop: AtomicBool,
}

impl Shared {
    fn push(&self, bytes: &[u8]) {
        let mut state = self.state.lock().unwrap();
        // Stop pulling from the pipe once the buffer is full instead of discarding
        // the oldest bytes: dropping mid-stream would tear ANSI escape sequences.
        // A full pipe makes conhost back-pressure the child, which is recoverable.
        while state.buf.len() >= self.capacity && !self.stop.load(Ordering::Acquire) {
            state = self.drained.wait_timeout(state, POLL_INTERVAL).unwrap().0;
        }
        state.buf.extend(bytes.iter().copied());
        self.ready.notify_all();
    }

    fn finish(&self, error: Option<String>) {
        let mut state = self.state.lock().unwrap();
        state.closed = true;
        if state.error.is_none() {
            state.error = error;
        }
        self.ready.notify_all();
    }
}

/// A ConPTY child process with a background thread draining its output pipe.
#[pyclass]
struct RealtimeConPtyProcess {
    process: Mutex<Option<Process>>,
    writer: Mutex<Option<PipeWriter>>,
    shared: Arc<Shared>,
    reader: Mutex<Option<JoinHandle<()>>>,
    pid: u32,
}

#[pymethods]
impl RealtimeConPtyProcess {
    fn pid(&self) -> u32 {
        self.pid
    }

    fn is_alive(&self) -> bool {
        self.process
            .lock()
            .unwrap()
            .as_ref()
            .map_or(false, |p| p.is_alive())
    }

    /// Starts a background thread draining the ConPTY output pipe.
    fn start_realtime_streaming(&self) -> PyResult<()> {
        let mut reader_slot = self.reader.lock().unwrap();
        if reader_slot.is_some() {
            return Ok(());
        }

        let mut guard = self.process.lock().unwrap();
        let process = guard.as_mut().ok_or_else(|| err("process is closed"))?;
        let mut pipe = process.output().map_err(err)?;
        // Poll instead of blocking: conhost keeps a duplicate of the output
        // handle alive, so a blocking read can outlive the child forever.
        pipe.blocking(false);

        let shared = Arc::clone(&self.shared);
        *reader_slot = Some(thread::spawn(move || {
            let mut chunk = [0u8; READ_CHUNK_SIZE];
            while !shared.stop.load(Ordering::Acquire) {
                match pipe.read(&mut chunk) {
                    Ok(0) => break,
                    Ok(n) => shared.push(&chunk[..n]),
                    Err(e) if e.kind() == ErrorKind::WouldBlock => thread::sleep(POLL_INTERVAL),
                    Err(e) if e.kind() == ErrorKind::BrokenPipe => break,
                    Err(e) => {
                        shared.finish(Some(e.to_string()));
                        return;
                    }
                }
            }
            shared.finish(None);
        }));

        Ok(())
    }

    /// Reads up to `size` buffered bytes, waiting at most `timeout_microseconds`.
    ///
    /// Returns `b""` when the timeout expires with nothing buffered.
    #[pyo3(signature = (size = READ_CHUNK_SIZE, timeout_microseconds = 0))]
    fn read_realtime<'py>(
        &self,
        py: Python<'py>,
        size: usize,
        timeout_microseconds: u64,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let shared = Arc::clone(&self.shared);
        let data = py.allow_threads(move || {
            let timeout = Duration::from_micros(timeout_microseconds);
            let start = Instant::now();
            let mut state = shared.state.lock().unwrap();
            while state.buf.is_empty() {
                if let Some(e) = state.error.clone() {
                    return Err(e);
                }
                if state.closed {
                    break;
                }
                let elapsed = start.elapsed();
                if elapsed >= timeout {
                    break;
                }
                state = shared.ready.wait_timeout(state, timeout - elapsed).unwrap().0;
            }
            let n = size.min(state.buf.len());
            let data = state.buf.drain(..n).collect::<Vec<u8>>();
            if n > 0 {
                shared.drained.notify_all();
            }
            Ok(data)
        });

        Ok(PyBytes::new_bound(py, &data.map_err(err)?))
    }

    fn write_realtime(&self, py: Python<'_>, data: Vec<u8>) -> PyResult<usize> {
        py.allow_threads(move || {
            let mut writer = self.writer.lock().unwrap();
            let writer = writer.as_mut().ok_or_else(|| err("input is closed"))?;
            writer.write_all(&data).map_err(err)?;
            writer.flush().map_err(err)?;
            Ok(data.len())
        })
    }

    fn resize(&self, cols: i16, rows: i16) -> PyResult<()> {
        self.process
            .lock()
            .unwrap()
            .as_mut()
            .ok_or_else(|| err("process is closed"))?
            .resize(cols, rows)
            .map_err(err)
    }

    fn terminate(&self, py: Python<'_>, code: u32) -> PyResult<()> {
        let result = match self.process.lock().unwrap().as_mut() {
            Some(process) => process.exit(code).map_err(err),
            None => Ok(()),
        };
        self.close(py);
        result
    }

    fn close(&self, py: Python<'_>) {
        self.shared.stop.store(true, Ordering::Release);
        self.shared.drained.notify_all();
        self.shared.finish(None);
        let handle = self.reader.lock().unwrap().take();
        py.allow_threads(move || {
            if let Some(handle) = handle {
                let _ = handle.join();
            }
        });
        drop(self.writer.lock().unwrap().take());
        drop(self.process.lock().unwrap().take());
    }
}

/// Spawns `command` inside a new pseudo console with a realtime output reader.
#[pyfunction]
#[pyo3(signature = (command, console_size = None, buffer_size = None))]
fn spawn_realtime(
    command: &str,
    console_size: Option<(i16, i16)>,
    buffer_size: Option<usize>,
) -> PyResult<RealtimeConPtyProcess> {
    let mut options = ProcessOptions::default();
    options.set_console_size(console_size);

    let mut process = options.spawn(Command::new(quote_program(command))).map_err(err)?;
    let pid = process.pid();
    let writer = process.input().map_err(err)?;

    let capacity = buffer_size.unwrap_or(DEFAULT_BUFFER_SIZE).max(READ_CHUNK_SIZE);

    Ok(RealtimeConPtyProcess {
        process: Mutex::new(Some(process)),
        writer: Mutex::new(Some(writer)),
        shared: Arc::new(Shared {
            state: Mutex::new(State {
                buf: VecDeque::with_capacity(capacity),
                closed: false,
                error: None,
            }),
            ready: Condvar::new(),
            drained: Condvar::new(),
            capacity,
            stop: AtomicBool::new(false),
        }),
        reader: Mutex::new(None),
        pid,
    })
}

/// The crate builds its command line by joining program and args with spaces and
/// no quoting, so an unquoted `C:\Program Files\...` would be split by CreateProcessW.
fn quote_program(command: &str) -> String {
    if command.contains(' ') && !command.starts_with('"') {
        format!("\"{command}\"")
    } else {
        command.to_owned()
    }
}

#[pymodule]
fn conpty(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RealtimeConPtyProcess>()?;
    m.add_function(wrap_pyfunction!(spawn_realtime, m)?)?;
    Ok(())
}
