import asyncio
from browser_use import Browser as BUBrowser

async def main():
    print("Attempting to instantiate browser_use.Browser without arguments...")
    try:
        bu_browser_naked = BUBrowser()
        print(f"Successfully instantiated.")
        print(f"Type of bu_browser_naked (BUBrowser() with no args): {type(bu_browser_naked)}")
        
        # Attempt to see if it has a connect method
        if hasattr(bu_browser_naked, 'connect'):
            print("bu_browser_naked HAS a 'connect' method.")
        else:
            print("bu_browser_naked does NOT have a 'connect' method.")

        # Attempt to see if it has a close method
        if hasattr(bu_browser_naked, 'close'):
            print("bu_browser_naked HAS a 'close' method.")
            # If it's async, it might need to be awaited, but don't call it here.
            if asyncio.iscoroutinefunction(bu_browser_naked.close):
                print("bu_browser_naked.close() is an async coroutine function.")
            else:
                print("bu_browser_naked.close() is a synchronous function.")
        else:
            print("bu_browser_naked does NOT have a 'close' method.")

    except Exception as e:
        print(f"Error during instantiation or type check: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(main()) 