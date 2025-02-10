from grpc_tools import protoc

# python -m grpc_tools.protoc -I=. \
#   --python_out=. --grpc_python_out=. \
#   ./web_protocol.proto
protoc.main(
    (
        "",
        "-I=.",
        "--python_out=./ws_protocol",
        "--pyi_out=./ws_protocol",
        "./web_protocol.proto",
    )
)