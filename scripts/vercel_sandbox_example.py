import asyncio

from dotenv import load_dotenv


load_dotenv(".env.local")


async def main() -> None:
    # Import lazily so the script can fail with a clearer message on Windows.
    from vercel.sandbox import AsyncSandbox

    sandbox = await AsyncSandbox.create()

    try:
        cmd = await sandbox.run_command("echo", ["Hello from Vercel Sandbox!"])
        stdout = await cmd.stdout()
        print(f"Message: {stdout.strip()}")
    finally:
        await sandbox.stop()


if __name__ == "__main__":
    asyncio.run(main())
