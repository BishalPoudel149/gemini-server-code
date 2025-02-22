import asyncio
import json
import os
import websockets
from google import genai
import base64
import signal

# Load API key from environment
os.environ['GOOGLE_API_KEY'] = 'AIzaSyBVbEoDEFMopCdj7P6NbGVv5_WfaZ0IQJA'
MODEL = "gemini-2.0-flash-exp"  # use your model ID

client = genai.Client(
  http_options={
    'api_version': 'v1alpha',
  }
)

async def gemini_session_handler(client_websocket: websockets.WebSocketServerProtocol):
    """Handles the interaction with Gemini API within a websocket session.

    Args:
        client_websocket: The websocket connection to the client.
    """
    try:
        config_message = await client_websocket.recv()
        config_data = json.loads(config_message)
        config = config_data.get("setup", {})
        config["system_instruction"] = """You are a highly intelligent and analytical financial assistant specialized in screen sharing sessions for financial markets, particularly forex exchanges. Your primary role is to analyze, interpret, and provide actionable insights based on the content being shared on the screen. Your responsibilities include:

            1. **Chart Analysis**:
            - Analyze candlestick charts, line charts, and other financial charts being shared.
            - Identify key patterns such as head and shoulders, double tops/bottoms, triangles, flags, and other technical patterns.
            - Detect support and resistance levels, trend lines, and moving averages.

            2. **Trend Analysis**:
            - Identify short-term, medium-term, and long-term trends in the market.
            - Analyze moving averages (e.g., SMA, EMA) and their crossovers.
            - Detect bullish or bearish trends based on price action and indicators.

            3. **Technical Indicators**:
            - Interpret technical indicators such as RSI, MACD, Bollinger Bands, Fibonacci retracement, and stochastic oscillators.
            - Provide insights into overbought/oversold conditions, momentum, and volatility.

            4. **Forecasting**:
            - Provide short-term and medium-term price forecasts based on technical analysis.
            - Highlight potential breakout or reversal points.
            - Suggest possible price targets and stop-loss levels.

            5. **Decision-Making**:
            - Provide actionable trading recommendations (e.g., buy, sell, hold) based on the analysis.
            - Suggest risk management strategies, including position sizing and stop-loss placement.
            - Highlight potential risks and uncertainties in the market.

            6. **Market Context**:
            - Incorporate macroeconomic factors (e.g., interest rates, inflation, geopolitical events) that may impact the forex market.
            - Analyze news events and their potential impact on currency pairs.

            7. **Communication**:
            - Use clear, concise, and professional language.
            - Avoid jargon unless explained.
            - Provide visual descriptions of charts and patterns when necessary.

            8. **Real-Time Assistance**:
            - Respond promptly to user queries during the screen sharing session.
            - Adapt your analysis based on real-time market movements.

            9. **Educational Insights**:
            - Explain complex concepts in a simple and understandable manner.
            - Provide educational insights to help the user improve their trading skills.

            10. **Focus on Forex**:
            - Prioritize forex market analysis, including major currency pairs (e.g., EUR/USD, GBP/USD, USD/JPY) and exotic pairs.
            - Analyze cross-currency pairs and their correlations.

            Example Scenarios:
            - If the user shares a candlestick chart, identify patterns like engulfing, doji, or hammer, and explain their significance.
            - If the user shares a chart with RSI and MACD, analyze the momentum and suggest potential entry/exit points.
            - If the user asks about the impact of a news event, provide a detailed analysis of how it might affect currency pairs.

            Your goal is to be a reliable, intelligent, and proactive financial assistant, helping the user make informed decisions in the forex market."""     

        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("Connected to Gemini API")

            async def send_to_gemini():
                """Sends messages from the client websocket to the Gemini API."""
                try:
                  async for message in client_websocket:
                      try:
                          data = json.loads(message)
                          if "realtime_input" in data:
                              for chunk in data["realtime_input"]["media_chunks"]:
                                  if chunk["mime_type"] == "audio/pcm":
                                      await session.send({"mime_type": "audio/pcm", "data": chunk["data"]})
                                      
                                  elif chunk["mime_type"] == "image/jpeg":
                                      await session.send({"mime_type": "image/jpeg", "data": chunk["data"]})
                                      
                      except Exception as e:
                          print(f"Error sending to Gemini: {e}")
                  print("Client connection closed (send)")
                except Exception as e:
                     print(f"Error sending to Gemini: {e}")
                finally:
                   print("send_to_gemini closed")



            async def receive_from_gemini():
                """Receives responses from the Gemini API and forwards them to the client, looping until turn is complete."""
                try:
                    while True:
                        try:
                            print("receiving from gemini")
                            async for response in session.receive():
                                if response.server_content is None:
                                    print(f'Unhandled server message! - {response}')
                                    continue

                                model_turn = response.server_content.model_turn
                                if model_turn:
                                    for part in model_turn.parts:
                                        if hasattr(part, 'text') and part.text is not None:
                                            await client_websocket.send(json.dumps({"text": part.text}))
                                        elif hasattr(part, 'inline_data') and part.inline_data is not None:
                                            print("audio mime_type:", part.inline_data.mime_type)
                                            base64_audio = base64.b64encode(part.inline_data.data).decode('utf-8')
                                            await client_websocket.send(json.dumps({
                                                "audio": base64_audio,
                                            }))
                                            print("audio received")

                                if response.server_content.turn_complete:
                                    print('\n<Turn complete>')
                        except websockets.exceptions.ConnectionClosedOK:
                            print("Client connection closed normally (receive)")
                            break  # Exit the loop if the connection is closed
                        except Exception as e:
                            print(f"Error receiving from Gemini: {e}")
                            break 

                except Exception as e:
                      print(f"Error receiving from Gemini: {e}")
                finally:
                      print("Gemini connection closed (receive)")


            # Start send loop
            send_task = asyncio.create_task(send_to_gemini())
            # Launch receive loop as a background task
            receive_task = asyncio.create_task(receive_from_gemini())
            await asyncio.gather(send_task, receive_task)


    except Exception as e:
        print(f"Error in Gemini session: {e}")
    finally:
        print("Gemini session closed.")


# async def main() -> None:
#     async with websockets.serve(gemini_session_handler, "localhost", 9083):
#         print("Running websocket server localhost:9083...")
#         await asyncio.Future()  # Keep the server running indefinitely

PORT = int(os.getenv("PORT", 8080))  # CF assigns a random port, fallback to 8080

async def main():
    async with websockets.serve(gemini_session_handler, "0.0.0.0", PORT):
        print(f"Running WebSocket server on ws://0.0.0.0:{PORT}")
        await asyncio.Future()  # Keep running indefinitely


if __name__ == "__main__":
    asyncio.run(main())