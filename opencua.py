# IP = "34.136.28.211"  # Replace with your VM's IP
import os
# read VM_IP
IP = os.getenv("VM_IP", "")
if not IP:
    raise ValueError("Please set the VM_IP environment variable to the IP address of your VM.")
else:
    print(f"Using VM IP: {IP}")
import logging

from numpy import size
logging.basicConfig(level=logging.INFO)
from cua_bench.computers.remote import RemoteDesktopSession

session = RemoteDesktopSession(
    api_url=f"http://{IP}:5000",
    os_type="windows",
)
async def main():
    await session.start()

    # Check screen size
    size = await session.interface.get_screen_size()
    print(size["width"], size["height"])  # e.g., 1024 768

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())