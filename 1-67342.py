#!/usr/bin/python3
import logging
import tkinter
import random
import serial
import string
import PIL
import tkinter as tk
from tkinter.ttk import *
from tkinter import *
import tkinter.font as font
import requests
import json
import qrcode

from threading import Timer, Thread
from PIL import ImageTk, Image
from io import BytesIO
import time
import os
import sys

from flask import Flask
import jwt
import datetime
from datetime import datetime
import pika

from gpiozero import OutputDevice as IOS
import RPi.GPIO as GPIO

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GPIO.setwarnings(False)

branchId = "68736ED4-8A1B-4C89-B8DC-AF07C4062AEB"
deviceId = "A36E7C4D-A523-4B54-8104-3C6628499E47"

baseUrl = "https://fitapi.fitstationcrm.com"

_http_headers = {"Connection": "close"}
_request_timeout = 15

fetchDataUrl = baseUrl + '/Entry/GetStartUpData'

session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[500,502,503,504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)


def safe_post(url, data):
    try:
        r = session.post(url, json=data, headers=_http_headers, timeout=_request_timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("POST ERROR:", e)
        return {"isSuccess": False, "data": {"message": "Connection error"}}


def safe_get(url):
    try:
        r = session.get(url, headers=_http_headers, timeout=10)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print("GET ERROR:", e)
        return None


sUobj = {'DeviceId': deviceId}
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
    data = startUpDataResult["data"]
    yon1_pin = int(data["yon1"])
    yon2_pin = int(data["yon2"])
    qrSuresi = int(data["qrSuresi"])
    beklemeSuresi = int(data["beklemeSuresi"])
    qrbeklemeSuresi = int(data["qrBeklemeSuresi"])
    isSerial = int(data["isSerial"])
    isGpio = int(data["isGpio"])
    queueName = data["queueName"]
    queueUrl = data["queueUrl"]


def CreateControls(container, bgColor, fgColor, text, x, y, fontx):
    lbl = Label(container, bg=bgColor, fg=fgColor)
    lbl.config(text=text)
    lbl.place(x=x, y=y)
    lbl['font'] = fontx
    return lbl


def numericFix(val):
    if val < 10:
        return "0" + str(val)
    return str(val)


def changeAscii(cr, dd):
    return chr(ord(cr) + int(dd))


def CreateQrCode():
    random_list = list(range(1,41))
    random.shuffle(random_list)

    indexer = numericFix(random_list[0])
    now = datetime.now()

    total = "QR"+indexer+numericFix(now.day)+numericFix(now.hour)+numericFix(now.minute)+numericFix(now.second)+deviceId

    newValue = "QR"+indexer
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


def SendExceptionInfo(e):
    try:
        url = baseUrl+'/Entry/GetExceptionInfo'
        myobj = {'EntryId': deviceId, 'BranchId': branchId, 'ErrorMessage': str(e)}
        session.post(url, json=myobj, headers=_http_headers, timeout=_request_timeout)
    except:
        pass


pencere = Tk()
pencere.configure(bg='black')
pencere.title("CRM GYM")

C = Canvas(pencere, bg="black")
pencere.after(1000, lambda: pencere.wm_attributes('-fullscreen', 'true'))

filename = None

img_data = safe_get(baseUrl + "/entry/yenifitstation.png")
if img_data:
    try:
        img = Image.open(BytesIO(img_data))
        filename = ImageTk.PhotoImage(img)
    except:
        pass

if filename is None:
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yenifitstation.png")
    if os.path.isfile(local):
        filename = PhotoImage(file=local)

if filename:
    background_label = Label(pencere, image=filename)
else:
    background_label = Label(pencere, bg='black')

background_label.place(x=100, y=90, relwidth=1, relheight=1)

myFont2 = font.Font(family='Castellar', size=24, weight='bold')
myFont = font.Font(family='Castellar', size=16, weight='bold')

AbonelikTarihi = CreateControls(pencere,"black","yellow","",600,100,myFont)
KalanGun = CreateControls(pencere,"black","yellow","",600,250,myFont)
KalanGunDeger = CreateControls(pencere,"black","white","",600,280,myFont2)
AbonelikTarihiDeger = CreateControls(pencere,"black","white","",600,130,myFont2)
SonucDeger = CreateControls(pencere,"black","white","",50,500,myFont2)

KartNoInput = Entry(pencere,bg='black')
KartNoInput.place(x=90,y=20,width=3,height=3)

yon1 = IOS(yon1_pin)
yon1.on()


def TurnstyleTurn(direction):
    try:
        yon1.on()
        time.sleep(0.25)
        yon1.off()
    except Exception as e:
        SendExceptionInfo(e)


def ValidationQuery(ali):
    try:
        if ali.get("isSuccess"):
            SonucDeger.config(text=ali["data"]["message"])
            KalanGunDeger.config(text=ali["data"]["daysLeft"])
            AbonelikTarihiDeger.config(text=ali["data"]["membershipDateText"])

            TurnstyleTurn(ali["data"]["type"])

            pathOfImage = ali["data"]["picture"]
            img_data = safe_get(pathOfImage)

            if img_data:
                img = Image.open(BytesIO(img_data))
                test = ImageTk.PhotoImage(img)
                label1 = tkinter.Label(image=test)
                label1.image = test
                label1.place(x=1600, y=1900)
                label1.after(beklemeSuresi, lambda: label1.destroy())
        else:
            SonucDeger.config(text=ali["data"]["message"])

    except Exception as e:
        SendExceptionInfo(e)


def dialog():
    try:
        url = baseUrl+'/Entry/GetMembershipInformation'
        myobj = {'EntryId': KartNoInput.get(), 'BranchId': branchId}
        KartNoInput.delete(0,"end")
        ali = safe_post(url,myobj)
        ValidationQuery(ali)
    except Exception as e:
        SendExceptionInfo(e)


def CreateQr():
    try:
        image = CreateQrCode()
        img = image.resize((325,325))
        tkimg = ImageTk.PhotoImage(img)
        label2 = tkinter.Label(pencere,image=tkimg)
        label2.place(x=840,y=50)
        label2.image = tkimg
        label2.after(29000,lambda: label2.destroy())
    except Exception as e:
        SendExceptionInfo(e)


class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


def callback(ch,method,properties,body):
    try:
        ali = json.loads(body)
        ValidationQuery(ali)
    except Exception as e:
        SendExceptionInfo(e)


def receiver():
    while True:
        try:
            parameters = pika.URLParameters(queueUrl)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.exchange_declare(exchange=queueName, exchange_type='fanout')

            result = channel.queue_declare(queue='',exclusive=True)
            queue_name = result.method.queue

            channel.queue_bind(exchange=queueName, queue=queue_name)

            channel.basic_consume(queue=queue_name,on_message_callback=callback,auto_ack=True)

            channel.start_consuming()

        except Exception as e:
            print("RabbitMQ reconnecting...",e)
            time.sleep(5)


CreateQr()
timer = RepeatTimer(qrSuresi, CreateQr)
timer.start()

receive_thread = Thread(target=receiver)
receive_thread.daemon=True
receive_thread.start()

KartNoInput.focus()
KartNoInput.bind("<Return>", lambda e: dialog())

pencere.mainloop()

sys.exit()