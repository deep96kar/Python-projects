import logging
import time
from pathlib import Path
from typing import List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logging.getLogger("selenium").setLevel(logging.WARNING)


class JarvisTTS:
    """
    Simple bridge: Python -> local HTML page -> Browser TTS.
    """

    def __init__(self, headless: bool = True, max_chunk_len: int = 400): #Chrome open then false
        self.max_chunk_len = max_chunk_len

        chrome_options = Options()
        # Keep Chrome visibly open by default; add headless only when requested
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--headless=new") # comment this line to see the browser

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options,
        )

        html_path = Path(__file__).parent / "index.html"
        if not html_path.exists():
            raise FileNotFoundError("index.html not found next to Text_SpeechToPython.py")

        self.driver.get(f"file:///{html_path}")

    # --- Context manager support ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.quit()

    # --- Internal helpers ---

    def _chunk_text(self, text: str) -> List[str]:
        """
        Breaks very long text into smaller chunks, preferably at sentence boundaries.
        """
        text = text.strip()
        if len(text) <= self.max_chunk_len:
            return [text]

        chunks = []
        current = []

        for sentence in text.replace("?", ".").replace("!", ".").split("."):
            sentence = sentence.strip()
            if not sentence:
                continue

            candidate = (". ".join(current + [sentence])).strip()
            if len(candidate) <= self.max_chunk_len:
                current.append(sentence)
            else:
                if current:
                    chunks.append(". ".join(current) + ".")
                current = [sentence]

        if current:
            chunks.append(". ".join(current) + ".")

        return chunks

    def speak(self, text: str):
        """
        Send text to browser TTS via index.html UI.
        """
        if not text or not text.strip():
            print("Jarvis Empty")
            return

        chunks = self._chunk_text(text)

        try:
            input_box = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "text"))
            )
            play_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "button"))
            )
        except Exception as e:
            print(f"Jarvis Error: {e}")
            return

        for idx, chunk in enumerate(chunks, start=1):
            try:
                input_box.clear()
                input_box.send_keys(chunk)
                print(f"[Jarvis]: {chunk}")
                play_button.click()

                # Wait for actual speech to complete
                try:
                    # Wait for status to change to "Speaking..."
                    WebDriverWait(self.driver, 2).until(
                        lambda d: "Speaking" in d.find_element(By.ID, "status").text
                    )
                    # Wait for status to show "Finished" or "Stopped"
                    WebDriverWait(self.driver, 60).until(
                        lambda d: "Finished" in d.find_element(By.ID, "status").text or "Stopped" in d.find_element(By.ID, "status").text
                    )
                except:
                    # Fallback to time-based wait if status checking fails
                    base = 0.8
                    per_char = 0.055  # ~18 chars/sec
                    sleep_duration = base + len(chunk) * per_char
                    if idx == len(chunks):
                        sleep_duration += 2.5
                    sleep_duration = min(sleep_duration, 20)
                    time.sleep(sleep_duration)

            except Exception as e:
                print(f"Jarvis Error chunk {idx}: {e}")
                break


    def speak_messages(self, messages: List[str]):
        """
        Speak a list of messages in order with simple progress logs.
        """
        total = len(messages)
        for idx, message in enumerate(messages, start=1):
            print(f"\n[Jarvis] Message {idx}/{total}")
            self.speak(message)


    def quit(self):
        try:
            self.driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    # Example usage
    with JarvisTTS(headless=False) as jarvis:
        jarvis.speak("Hello, I am the upgraded Jarvis. I support longer messages now.")
        jarvis.speak("You can control my voice, rate, and pitch from the browser window.")
        long_text = (
            "This is a long text example to demonstrate the chunking functionality of Jarvis TTS. "
            "It will break this text into smaller chunks to ensure that the browser's text-to-speech "
            "engine can handle it without issues. Each chunk will be spoken sequentially, with appropriate "
            "delays to allow for the speech to complete before moving on to the next chunk. "
            "This way, even very long messages can be effectively communicated using Jarvis TTS."
        )
        jarvis.speak(long_text)
        print("\n[Jarvis] All messages have been spoken successfully!")