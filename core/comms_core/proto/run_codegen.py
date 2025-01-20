from grpc_tools import protoc

# python -m grpc_tools.protoc -I=. \
#   --python_out=. --grpc_python_out=. \
#   ./terminalez.proto
protoc.main(
    (
        "",
        "-I=.",
        "--python_out=./terminalez",
        "--pyi_out=./terminalez",
        "--grpc_python_out=./terminalez",
        "./terminalez.proto",
    )
)