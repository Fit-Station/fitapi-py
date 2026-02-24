#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import ssl
import random
import string
import traceback
import tkinter as tk
import tkinter.font as font
from tkinter import Tk, Canvas, Label, Entry

from threading import Timer, Thread
from io import BytesIO

import requests
from requests.exceptions import ConnectionError, ReadTimeout, SSLError
from requests.exceptions import ChunkedEncodingError

import qrcode
from PIL import ImageTk, Image

import pika
from gpiozero import OutputDevice as IOS
import RPi.GPIO as GPIO
import atexit

# -----------------------------------------------------------------------------
# AYARLAR
# -----------------------------------------------------------------------------
DEBUG_TURNIKE_LOG = False

branchId = "68736ED4-8A1B-4C89-B8DC-AF07C4062AEB"
deviceId = "A36E7C4D-A523-4B54-8104-3C6628499E47"
baseUrl = "https://fitapi.fitstationcrm.com"

fetchDataUrl = baseUrl + "/Entry/GetStartUpData"

REQUEST_TIMEOUT = 15
GET_TIMEOUT = 10

BASE_HEADERS = {
    "Connection": "close",
    "Accept": "application/json",
    "Accept-Encoding": "identity",  # gzip/chunk karmaşasını azaltır
    "Content-Type": "application/json",
}

GET_HEADERS = {
    "Connection": "close",
    "Accept-Encoding": "identity",
}

GPIO.setwarnings(False)

# -----------------------------------------------------------------------------
# TEK INSTANCE LOCK (GPIO busy'nin en yaygın sebebi)
# -----------------------------------------------------------------------------
LOCK_FILE = "/tmp/turnike.lock"
try:
    lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_RDWR)
except FileExistsError:
    print("[LOCK] Uygulama zaten calisiyor. Cikiliyor.")
    sys.exit(0)

def _cleanup_lock():
    try:
        os.close(lock_fd)
    except:
        pass
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass

atexit.register(_cleanup_lock)

# -----------------------------------------------------------------------------
# NETWORK: STABIL SAFE GET/POST
# -----------------------------------------------------------------------------
def safe_post(url, data, tries=5, backoff=1.0):
    last_err = None
    payload = json.dumps(data).encode("utf-8")

    for i in range(tries):
        try:
            r = requests.post(
                url,
                data=payload,
                headers=BASE_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except (ChunkedEncodingError, ConnectionError, ReadTimeout, SSLError) as e:
            last_err = e
            time.sleep(backoff * (i + 1))
        except Exception as e:
            last_err = e
            break

    print("POST ERROR URL:", url)
    print("POST ERROR:", last_err)
    if DEBUG_TURNIKE_LOG:
        traceback.print_exc()
    return {"isSuccess": False, "data": {"message": "Connection error"}}


def safe_get(url, tries=5, backoff=1.0):
    last_err = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=GET_HEADERS, timeout=GET_TIMEOUT)
            r.raise_for_status()
            return r.content
        except (ChunkedEncodingError, ConnectionError, ReadTimeout, SSLError) as e:
            last_err = e
            time.sleep(backoff * (i + 1))
        except Exception as e:
            last_err = e
            break

    print("GET ERROR URL:", url, "|", last_err)
    if DEBUG_TURNIKE_LOG:
        traceback.print_exc()
    return None


def SendExceptionInfo(e):
    try:
        url = baseUrl + "/Entry/GetExceptionInfo"
        myobj = {"EntryId": deviceId, "BranchId": branchId, "ErrorMessage": str(e)}
        # Bu kısım kritik değil; hata olursa sessiz geç
        requests.post(url, data=json.dumps(myobj).encode("utf-8"), headers=BASE_HEADERS, timeout=REQUEST_TIMEOUT)
    except:
        pass


# -----------------------------------------------------------------------------
# STARTUP CONFIG (old.py ile aynı besleme: isSuccess ise data içinden doğrudan al)
# -----------------------------------------------------------------------------
sUobj = {"DeviceId": deviceId}
startUpDataResult = safe_post(fetchDataUrl, sUobj)

yon1_pin = 17
yon2_pin = 18
qrSuresi = 30
beklemeSuresi = 5000
qrbeklemeSuresi = 30000
isSerial = 0
isGpio = 1
queueName = ""
queueUrl = ""

if startUpDataResult.get("isSuccess"):
    yon1_pin = int(startUpDataResult["data"]["yon1"])
    yon2_pin = int(startUpDataResult["data"]["yon2"])
    qrSuresi = int(startUpDataResult["data"]["qrSuresi"])
    beklemeSuresi = int(startUpDataResult["data"]["beklemeSuresi"])
    qrbeklemeSuresi = int(startUpDataResult["data"]["qrBeklemeSuresi"])
    isSerial = int(startUpDataResult["data"]["isSerial"])
    isGpio = int(startUpDataResult["data"]["isGpio"])
    queueName = startUpDataResult["data"]["queueName"]
    queueUrl = startUpDataResult["data"]["queueUrl"]


# -----------------------------------------------------------------------------
# UI HELPERS
# -----------------------------------------------------------------------------
def CreateControls(container, bgColor, fgColor, text, x, y, fontx):
    lbl = Label(container, bg=bgColor, fg=fgColor)
    lbl.config(text=text)
    lbl.place(x=x, y=y)
    lbl["font"] = fontx
    return lbl


def numericFix(val):
    return "0" + str(val) if val < 10 else str(val)


def changeAscii(cr, dd):
    return chr(ord(cr) + int(dd))


def CreateQrCode():
    random_list = list(range(1, 41))
    random.shuffle(random_list)

    indexer = numericFix(random_list[0])
    now = time.localtime()

    # orijinaliniz datetime ileydi; aynı mantık
    day = numericFix(now.tm_mday)
    hour = numericFix(now.tm_hour)
    minute = numericFix(now.tm_min)
    second = numericFix(now.tm_sec)

    total = "QR" + indexer + day + hour + minute + second + deviceId

    newValue = "QR" + indexer
    sayac = 0

    for char in total:
        sayac += 1
        if sayac > 4:
            if sayac % 2 == 0:
                newValue += changeAscii(char, random_list[0])
            else:
                newValue += changeAscii(char, -random_list[0])

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(newValue)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


# -----------------------------------------------------------------------------
# GPIO
# -----------------------------------------------------------------------------
yon1 = None
yon2 = None

def init_gpio():
    """old.py gibi: yon1 her zaman oluşturulur, başlangıçta on()."""
    global yon1, yon2
    try:
        yon1 = IOS(yon1_pin)
        yon1.on()
    except Exception as e:
        print(f"[GPIO] Pin {yon1_pin} baslatilamadi (GPIO busy): {e}")
        if DEBUG_TURNIKE_LOG:
            traceback.print_exc()
        yon1 = None

    try:
        yon2 = IOS(yon2_pin)
        yon2.off()
    except Exception as e:
        print(f"[GPIO] Pin {yon2_pin} baslatilamadi: {e}")
        yon2 = None

def TurnstyleTurn(direction):
    """old.py gibi: her zaman yon1 ile dönüş (on -> 0.25s -> off)."""
    try:
        if yon1 is not None:
            yon1.on()
            time.sleep(0.25)
            yon1.off()
    except Exception as e:
        SendExceptionInfo(e)


def cleanup_gpio():
    global yon1, yon2
    try:
        if yon1 is not None:
            yon1.off()
            yon1.close()
    except:
        pass
    try:
        if yon2 is not None:
            yon2.off()
            yon2.close()
    except:
        pass
    try:
        GPIO.cleanup()
    except:
        pass

atexit.register(cleanup_gpio)

# -----------------------------------------------------------------------------
# UI SETUP
# -----------------------------------------------------------------------------
pencere = Tk()
pencere.configure(bg="black")
pencere.title("CRM GYM")

C = Canvas(pencere, bg="black")
pencere.after(1000, lambda: pencere.wm_attributes("-fullscreen", "true"))

filename = None

# background image
img_data = safe_get(baseUrl + "/entry/yenifitstation.png")
if img_data:
    try:
        img = Image.open(BytesIO(img_data))
        filename = ImageTk.PhotoImage(img)
    except:
        filename = None

if filename is None:
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yenifitstation.png")
    if os.path.isfile(local):
        try:
            filename = ImageTk.PhotoImage(Image.open(local))
        except:
            filename = None

if filename:
    background_label = Label(pencere, image=filename)
else:
    background_label = Label(pencere, bg="black")

background_label.place(x=100, y=90, relwidth=1, relheight=1)

myFont2 = font.Font(family="Castellar", size=24, weight="bold")
myFont = font.Font(family="Castellar", size=16, weight="bold")

AbonelikTarihi = CreateControls(pencere, "black", "yellow", "", 600, 100, myFont)
KalanGun = CreateControls(pencere, "black", "yellow", "", 600, 250, myFont)
KalanGunDeger = CreateControls(pencere, "black", "white", "", 600, 280, myFont2)
AbonelikTarihiDeger = CreateControls(pencere, "black", "white", "", 600, 130, myFont2)
SonucDeger = CreateControls(pencere, "black", "white", "", 50, 500, myFont2)

KartNoInput = Entry(pencere, bg="black")
KartNoInput.place(x=90, y=20, width=3, height=3)


# -----------------------------------------------------------------------------
# UI UPDATE (THREAD SAFE)
# -----------------------------------------------------------------------------
def ValidationQuery(ali):
    """
    Bu fonksiyon UI thread'inde çalışmalı.
    """
    try:
        if ali.get("isSuccess"):
            data = ali.get("data", {})
            SonucDeger.config(text=str(data.get("message", "")))
            KalanGunDeger.config(text=str(data.get("daysLeft", "")))
            AbonelikTarihiDeger.config(text=str(data.get("membershipDateText", "")))

            TurnstyleTurn(data.get("type", 1))

            pathOfImage = data.get("picture")
            if pathOfImage:
                img_data = safe_get(pathOfImage)
                if img_data:
                    img = Image.open(BytesIO(img_data))
                    test = ImageTk.PhotoImage(img)
                    label1 = tk.Label(pencere, image=test)
                    label1.image = test
                    label1.place(x=1600, y=1900)
                    label1.after(beklemeSuresi, lambda: label1.destroy())
        else:
            SonucDeger.config(text=str(ali.get("data", {}).get("message", "")))

    except Exception as e:
        SendExceptionInfo(e)


def dialog():
    try:
        url = baseUrl + "/Entry/GetMembershipInformation"
        myobj = {"EntryId": KartNoInput.get(), "BranchId": branchId}
        KartNoInput.delete(0, "end")
        ali = safe_post(url, myobj)
        ValidationQuery(ali)
    except Exception as e:
        SendExceptionInfo(e)


def CreateQr():
    try:
        image = CreateQrCode()
        img = image.resize((325, 325))
        tkimg = ImageTk.PhotoImage(img)
        label2 = tk.Label(pencere, image=tkimg)
        label2.place(x=840, y=50)
        label2.image = tkimg
        label2.after(qrbeklemeSuresi - 1000, lambda: label2.destroy())
    except Exception as e:
        SendExceptionInfo(e)


# -----------------------------------------------------------------------------
# TIMER
# -----------------------------------------------------------------------------
class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            try:
                self.function(*self.args, **self.kwargs)
            except Exception as e:
                SendExceptionInfo(e)


# -----------------------------------------------------------------------------
# RABBITMQ
# -----------------------------------------------------------------------------
def callback(ch, method, properties, body):
    """
    Rabbit thread'inden UI'ye dokunma!
    after() ile UI thread'ine aktar.
    """
    try:
        ali = json.loads(body)
        pencere.after(0, lambda: ValidationQuery(ali))
    except Exception as e:
        SendExceptionInfo(e)


def receiver():
    reconnect_delay = 15
    while True:
        if not (queueName and queueUrl):
            time.sleep(reconnect_delay)
            continue

        try:
            parameters = pika.URLParameters(queueUrl)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.exchange_declare(exchange=queueName, exchange_type="fanout")

            result = channel.queue_declare(queue="", exclusive=True)
            queue_name = result.method.queue

            channel.queue_bind(exchange=queueName, queue=queue_name)

            channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

            reconnect_delay = 15
            channel.start_consuming()

        except Exception as e:
            print("RabbitMQ reconnecting...", e)
            time.sleep(reconnect_delay)


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    init_gpio()

    CreateQr()
    timer = RepeatTimer(qrSuresi, CreateQr)
    timer.daemon = True
    timer.start()

    receive_thread = Thread(target=receiver, daemon=True)
    receive_thread.start()

    KartNoInput.focus()
    KartNoInput.bind("<Return>", lambda e: dialog())

    try:
        pencere.mainloop()
    finally:
        cleanup_gpio()
        _cleanup_lock()


if __name__ == "__main__":
    main()