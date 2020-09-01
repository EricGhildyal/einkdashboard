import os
import pickle
import time
from datetime import datetime, timedelta

# 3rd party imports
from dotenv import load_dotenv
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
# from waveshare_epd import epd7in5_V2
# import time
# from PIL import Image, ImageDraw, ImageFont
# import traceback

UPTIMEROBOT_API_URL = "https://api.uptimerobot.com/v2"
SENTRY_API_URL = "https://sentry.io/api/0"
GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_down_monitors():
    down = []
    res = requests.post(f"{UPTIMEROBOT_API_URL}/getMonitors",
                        data = f"api_key={os.getenv('UPTIMEROBOT_API_KEY')}&format=json&statuses=8-9",
                        headers = {
                            "Content-Type": "application/x-www-form-urlencoded"
                        })
    if res.status_code == 200 and res.json()['stat'] == "ok":
        return [monitor['friendly_name'] for monitor in res.json()['monitors']]
    print(f"Error getting down monitors: {res.json()}")
    return None

def get_service_ratios():
    ratios = {}
    res = requests.post(f"{UPTIMEROBOT_API_URL}/getMonitors",
                        data = f"api_key={os.getenv('UPTIMEROBOT_API_KEY')}&format=json&custom_uptime_ratios=30",
                        headers = {
                            "Content-Type": "application/x-www-form-urlencoded"
                        })
    if res.status_code == 200 and res.json()['stat'] == "ok":
        for monitor in res.json()['monitors']: # we want an avg over all the services on different clusters
            serv_name = monitor['friendly_name'].split(" ")[0]
            if serv_name in ratios:
                ratios[serv_name].append(float(monitor['custom_uptime_ratio']))
            else:
                ratios[serv_name] = [float(monitor['custom_uptime_ratio'])]
        for ratio in ratios:
            if isinstance(ratios[ratio], list):
                ratios[ratio] = round(sum(ratios[ratio]) / len(ratios[ratio]), 4)
        return ratios
    print(f"Error getting service ratios: {res.json()}")
    return None

def get_sentry_events(project):
    out = []
    res = requests.get(f"{SENTRY_API_URL}/projects/root-health/{project}/issues/?statsPeriod=24h", 
                       headers = {"Authorization": f"Bearer {os.getenv('SENTRY_TOKEN')}"}
                      )
    if res.status_code == 200:
        events = res.json()[:5] # only grab first 5
        for event in events:
            out.append({
                "title": event['title'],
                "culprit": event['culprit'],
                "count": event['count'] 
            })
        return out
    print(f"Error getting sentry events: {res.json()}")
    return None

def get_cal_events(num):
    credentials = service_account.Credentials.from_service_account_file(os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE'), scopes=GOOGLE_SCOPES)
    delegated_credentials = credentials.with_subject(os.getenv('GOOGLE_SUBJECT'))
    service = build('calendar', 'v3', credentials=delegated_credentials)
    now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events = service.events().list(calendarId=os.getenv('GOOGLE_SUBJECT'),timeMin=now,maxResults=num,orderBy='startTime',singleEvents=True).execute()
    print(events)

def display_test(uptimes):
    try:
        print("init and clear")
        epd = epd7in5_V2.EPD()
        epd.init()
        epd.Clear()
        print("/init and clear")
        display_font = ImageFont.truetype('Righteous-Regular.ttf', 40)
        display_font_sm = ImageFont.truetype('Righteous-Regular.ttf', 20)
        number_font = ImageFont.truetype('KellySlab-Regular.ttf', 35)
        image = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame
        draw = ImageDraw.Draw(image)
        draw.text((10, 0), 'Uptime', font = display_font, fill = 0)
        x = 10
        y = 65
        for serv, ratio in uptimes.items():
            draw.text((x, y), serv, font = display_font_sm, fill = 0)
            y += 25
            draw.text((x, y), ratio, font = number_font, fill = 0)
            y += 30
        draw.line((0, 60, 150, 60), fill = 0, width = 3)
        draw.line((150, 0, 150, epd.height), fill = 0, width = 3)
        print("displaying")
        epd.display(epd.getbuffer(image))
        print("/displaying")
    except IOError as err:
        print(f"Error: {err}")
    except KeyboardInterrupt:    
        print("^C")
        epd7in5_V2.epdconfig.module_exit()
        exit()

def main():
    uptimes = get_service_ratios()
    display_test(uptimes)
    # while True:
    #     print("---------------- Down Monitors --------------------")
    #     print(get_down_monitors())
    #     print("---------------- 30-day Statistics --------------------")
    #     print(get_service_ratios())
    #     print("----------------- Frontend Sentry ---------------------")
    #     print(get_sentry_events("frontend"))
    #     print("----------------- Backend Sentry ---------------------")
    #     print(get_sentry_events("backend"))
    #     # print("---------------- Calendar --------------------")
    #     # # print(get_cal_events(5))
    #     # print("------------------------------------------")
    #     time.sleep(180) # sleep 3 mins

if __name__ == "__main__":
    load_dotenv()
    main()
