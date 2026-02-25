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
import requests as requests
import json
import qrcode

from threading import Timer
from threading import Thread
from PIL import ImageTk, Image
from io import BytesIO
import time
import os
import sys

from flask import Flask
import jwt
import datetime
from datetime import datetime
from threading import Timer
import pika
import json
from gpiozero import OutputDevice as IOS

from pika import exceptions

import RPi.GPIO as GPIO
GPIO.setwarnings(False)


branchId = "68736ED4-8A1B-4C89-B8DC-AF07C4062AEB"
deviceId = "A36E7C4D-A523-4B54-8104-3C6628499E47"

#Canik
global yon1_pin
global yon2_pin
global yon1
global yon2
global qrSuresi
global beklemeSuresi
global qrbeklemeSuresi
global isSerial
global isGpio
global queueName
global queueUrl
global baseUrl



baseUrl = "https://fitapi.fitstationcrm.com"
fetchDataUrl = baseUrl+'/Entry/GetStartUpData'
sUobj = {'DeviceId': deviceId}
resultOfPost = requests.post(fetchDataUrl, json=sUobj)
startUpDataResult = json.loads(resultOfPost.text)
if startUpDataResult["isSuccess"]:
    yon1_pin = int(startUpDataResult["data"]["yon1"])
    yon2_pin = int(startUpDataResult["data"]["yon2"])
    qrSuresi = int(startUpDataResult["data"]["qrSuresi"])
    beklemeSuresi = int(startUpDataResult["data"]["beklemeSuresi"])
    qrbeklemeSuresi = int(startUpDataResult["data"]["qrBeklemeSuresi"])
    isSerial = int(startUpDataResult["data"]["isSerial"])
    isGpio = int(startUpDataResult["data"]["isGpio"])
    queueName = startUpDataResult["data"]["queueName"]
    queueUrl = startUpDataResult["data"]["queueUrl"]
    
def CreateControls(container, bgColor, fgColor, text, xCoordinate, yCoordinate, font, type):
    if type == "label":
        lbl = Label(container, bg=bgColor, fg=fgColor)
        lbl.config(text=text)
        lbl.place(x=xCoordinate, y=yCoordinate)
        lbl['font'] = font
        return lbl 

def numericFix(val):    
    val_text=""
    if val<10:
        val_text="0"+str(val)
    else:
        val_text=str(val)
    print(val_text)
    return val_text

def changeAscii(cr,dd):
    numvl=int(ord(cr))
    tempValue=numvl+int(dd)
    return chr(tempValue)

def CreateQrCode():
    _indexer_value=""
    _day_value=""
    _hour_value=""
    _minute_value=""
    _second_value=""
    _branchId_value=""
    random_list=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40]
    random.shuffle(random_list)
    random_indexer=random_list[0]
    _indexer_value=numericFix(random_indexer)
    _day_value=numericFix(datetime.now().day)
    _hour_value=numericFix(datetime.now().hour)
    _minute_value=numericFix(datetime.now().minute)
    _second_value=numericFix(datetime.now().second)
    _customerId_value=deviceId

    totalValue="QR"+_indexer_value+_day_value+_hour_value+_minute_value+_second_value+_customerId_value;
    newValue="QR"+_indexer_value
    sayac=0
    for char in totalValue:
        sayac=sayac+1
        if sayac>4:
            test=sayac%2
            if test==0:
                newValue=newValue+changeAscii(char,random_indexer)
            else:
                newValue = newValue + changeAscii(char, random_indexer*-1)
    print(newValue)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    print(totalValue)
    qr.add_data(newValue)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def OnKeyPress(key):
    try:
        if ord(key.char) == 13:
            dialog()
    except:
        print(f"cift tusa bastin hatasi")

pencere = Tk()
pencere.configure(bg='black')
pencere.title("CRM GYM")
# resim arkaplan
C = Canvas(pencere, bg="black")
#pencere.attributes('-fullscreen', True)
pencere.after(1000, lambda: pencere.wm_attributes('-fullscreen', 'true'))
filename = PhotoImage(file="/home/admin/Bookshelf/KUM/yenifitstation.png")
background_label = Label(pencere, image=filename)
background_label.configure(bg='black')
background_label.place(x=100, y=90, relwidth=1, relheight=1)

# resim arkaplan SON
myFont2 = font.Font(family='Castellar', size=24, weight='bold')
myFont = font.Font(family='Castellar', size=16, weight='bold')
AbonelikTarihi = CreateControls(pencere, "black", "yellow", "", 600, 100, myFont, "label")
KalanGun = CreateControls(pencere, "black", "yellow", "", 600, 250, myFont, "label")
KalanGunDeger = CreateControls(pencere, "black", "white", "", 600, 280, myFont2, "label")
AbonelikTarihiDeger = CreateControls(pencere, "black", "white", "", 600, 130, myFont2, "label")
SonucDeger = CreateControls(pencere, "black", "white", "", 50, 500, myFont2, "label")

KartNoInput = Entry(pencere, bg='black') 
KartNoInput.config(bd=2)
KartNoInput.place(x=90, y=20, width=3, height=3)
KabulDugmesi = Button(pencere, width=1, height=1, highlightthickness=0, bd=0, bg='black')  # , command=dialog)
KabulDugmesi.place(x=0, y=0)
KartNoInput.focus()
KartNoInput.bind("<Key>", OnKeyPress)
yon1 = IOS(yon1_pin)
#yon2 = IOS(yon2_pin)
yon1.on()
#yon2.on()

def callback(ch, method, properties, body):
    ali = json.loads(body)
    ValidationQuery(ali)







def receiver():
    # while True:
    try:
        connection = None
        parameters = pika.URLParameters(queueUrl)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=queueName, exchange_type='fanout')
        result = channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange=queueName, queue=queue_name)
        channel.basic_consume(queue=queue_name, on_message_callback=callback , auto_ack=True, exclusive=True)
        channel.start_consuming()
    except Exception as tt:
        channel.stop_consuming()
        connection.close()
        raise tt

def TurnstyleTurn(direction):
    try:
        yon1.on()
        time.sleep(0.25)
        yon1.off()
    except Exception as er:
        KartNoInput.focus()
        SendExceptionInfo(er)
class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)
def dialog():
    try:
        url = baseUrl+'/Entry/GetMembershipInformation'
        myobj = {'EntryId': KartNoInput.get(), 'BranchId': branchId}
        KartNoInput.delete(0, "end")
        x = requests.post(url, json=myobj)
        ali = json.loads(x.text)
        ValidationQuery(ali)
    except Exception as er:
        print(er)
        KartNoInput.focus()
        SendExceptionInfo(er)
    SonucDeger.after(beklemeSuresi, lambda: SonucDeger.config(text=""))
    KalanGunDeger.after(beklemeSuresi, lambda: KalanGunDeger.config(text=""))
    AbonelikTarihiDeger.after(beklemeSuresi, lambda: AbonelikTarihiDeger.config(text=""))
    AbonelikTarihi.after(beklemeSuresi, lambda: AbonelikTarihi.config(text=""))
    KalanGun.after(beklemeSuresi, lambda: KalanGun.config(text=""))
def ValidationQuery(ali):
    try:
        if ali["isSuccess"]:
            SonucDeger.config(text=ali["data"]["message"])
            KalanGunDeger.config(text=ali["data"]["daysLeft"])
            AbonelikTarihiDeger.config(text=ali["data"]["membershipDateText"])
            AbonelikTarihi.config(text="ABONELÄ°K TARÄ°HÄ°:")
            KalanGun.config(text="KALAN GÃœN SAYISI:")
            pathOfImage = ali["data"]["picture"]
            TurnstyleTurn(ali["data"]["type"])
            label1 = tkinter.Label()
            try:
                try:
                    response = requests.get(pathOfImage)
                    img_data = response.content
                    img = Image.open(BytesIO(img_data))
                    test = ImageTk.PhotoImage(img)
                    label1 = tkinter.Label(image=test)
                    label1.image = test
                    label1.place(x=1600, y=1900)
                    label1.grid()
                    label1.after(beklemeSuresi, lambda: label1.destroy())
                except Exception as er:
                    label1.after(beklemeSuresi, lambda: label1.destroy())
                    SendExceptionInfo(er)
                SonucDeger.after(beklemeSuresi, lambda: SonucDeger.config(text=""))
                KalanGunDeger.after(beklemeSuresi, lambda: KalanGunDeger.config(text=""))
                AbonelikTarihiDeger.after(beklemeSuresi, lambda: AbonelikTarihiDeger.config(text=""))
                AbonelikTarihi.after(beklemeSuresi, lambda: AbonelikTarihi.config(text=""))
                KalanGun.after(beklemeSuresi, lambda: KalanGun.config(text=""))
            except Exception  as er:
                label1.after(beklemeSuresi, lambda: label1.destroy())
                KartNoInput.focus()
                SendExceptionInfo(er)
            # Position image
        else:
            SonucDeger.config(text=ali["data"]["message"])
    except Exception  as er:
        KartNoInput.focus()
        SendExceptionInfo(er)
def CreateQr():
    try:
        image = CreateQrCode()
        test2 = image.resize((325, 325))
        test3 = ImageTk.PhotoImage(test2)
        label2 = tkinter.Label(pencere, image=test3)
        label2.place(x=840, y=50)
        label2.image = test3
        label2.after(29000, lambda: label2.destroy())
    except Exception as er:
        KartNoInput.focus()
        SendExceptionInfo(er)



def SendExceptionInfo(e):
    try:
        url = baseUrl+'/Entry/GetExceptionInfo'
        myobj = {'EntryId': deviceId,  'BranchId': branchId, 'ErrorMessage': str(e)}
        requests.post(url, json=myobj)
    except:
        SonucDeger.config(text="Hata olustu")
        SonucDeger.after(beklemeSuresi, lambda: SonucDeger.config(text=""))


CreateQr()
timer = RepeatTimer(qrSuresi, CreateQr)
timer.start()


KabulDugmesi.config(command = dialog)
receive_thread = Thread(target = receiver)
receive_thread.daemon = True
receive_thread.start()
pencere.mainloop()

sys.exit()



