import argparse
import asyncio
from main import run_multi_agent_system

def main():
    parser = argparse.ArgumentParser(description="Ticket Tracking Multi-Agent CLI")
    parser.add_argument("--run", action="store_true", help="Execute the multi-agent workflow")
    args = parser.parse_args()
    
    if args.run:
        asyncio.run(run_multi_agent_system())
    else:
        print("Use --run to execute the agent pipeline.")

if __name__ == "__main__":
    main()
