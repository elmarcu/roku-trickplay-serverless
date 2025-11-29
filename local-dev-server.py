"""Local development server mimicking AWS Lambda runtime."""

import json
import os
import sys
from importlib import import_module
from typing import Any, Callable, Dict

from shared.logger import StructuredLogger


class LocalLambdaContext:
    """Mock Lambda context object."""

    def __init__(self, function_name: str, request_id: str):
        self.function_name = function_name
        self.request_id = request_id
        self.log_group_name = f"/aws/lambda/{function_name}"
        self.log_stream_name = "local-dev"
        self.memory_limit_in_mb = 512
        self.invoked_function_arn = f"arn:aws:lambda:us-east-1:000000000000:function:{function_name}"


def load_lambda_handler(lambda_dir: str) -> Callable[[Dict[str, Any], Any], Dict[str, Any]]:
    """Dynamically load Lambda handler from module."""
    try:
        # Add lambda directory to path
        sys.path.insert(0, lambda_dir)
        sys.path.insert(0, "/app")

        # Import handler module
        handler_module = import_module("handler")
        return handler_module.lambda_handler
    except Exception as e:
        StructuredLogger.error("Failed to load Lambda handler", exception=e)
        raise


def invoke_function(function_name: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke Lambda function locally."""
    try:
        function_dir = f"/app/src/{function_name}"

        StructuredLogger.info(
            "Invoking Lambda function",
            function_name=function_name,
            function_dir=function_dir,
        )

        # Load handler
        handler = load_lambda_handler(function_dir)

        # Create mock context
        context = LocalLambdaContext(
            function_name=function_name,
            request_id=f"local-{os.urandom(8).hex()}",
        )

        # Invoke function
        result = handler(event, context)

        return result

    except Exception as e:
        StructuredLogger.error(
            "Function invocation failed",
            function_name=function_name,
            exception=e,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


def main():
    """Start local development server."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class LambdaRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                request_data = json.loads(body)
                function_name = request_data.get("function_name")
                event = request_data.get("event", {})

                if not function_name:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing function_name"}).encode())
                    return

                result = invoke_function(function_name, event)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        def log_message(self, format, *args):
            """Suppress default logging."""
            pass

    server = HTTPServer(("0.0.0.0", 8000), LambdaRequestHandler)
    StructuredLogger.info("Local Lambda development server started", port=8000)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        StructuredLogger.info("Server shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
