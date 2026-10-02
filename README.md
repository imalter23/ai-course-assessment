# ai-course-assessment
AI in5 Days
# Event Ticket Timing Tracker Agent

## Overview
An intelligent concierge agent designed to analyze historical event pricing, track days remaining until an event, and recommend the precise optimal time to purchase tickets to maximize savings.

## Architecture & Core Components
- **Tool Design**: Simulated API connectors to fetch pricing trends and historical data.
- **Orchestration & Logic**: Decision-tree matrix evaluating countdown timelines against historical price troughs.
- **Context & Memory**: Maintains target event dates and pricing state.
- **Observability**: Built-in CLI tracing logs for each tool execution and decision step.

## How to Run
```bash
python main.py
