"""
Server entry point for Enhanced FDA Explorer
"""

def main():
    """Main entry point for the server"""
    from .api import run_api_server
    run_api_server()

if __name__ == "__main__":
    main()