import os
import pickle
import time
from datetime import datetime, timedelta

# 3rd party imports
from dotenv import load_dotenv
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from waveshare_epd import epd7in5_V2
from PIL import Image, ImageDraw, ImageFont
import traceback

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
                ratios[ratio] = round(sum(ratios[ratio]) / len(ratios[ratio]), 2)
        return ratios
    print(f"Error getting service ratios: {res.json()}")
    return None

def get_sentry_events(project):
    out = []
    res = requests.get(f"{SENTRY_API_URL}/projects/root-health/{project}/issues/?statsPeriod=24h", 
                       headers = {"Authorization": f"Bearer {os.getenv('SENTRY_TOKEN')}"}
                      )
    if res.status_code == 200:
        events = res.json()[:3] # only grab first 3
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

def display_test(uptimes, down, backend_events):
    try:
        print("init and clear")
        epd = epd7in5_V2.EPD()
        epd.init()
        epd.Clear()
        print("/init and clear")
        display_font = ImageFont.truetype('Righteous-Regular.ttf', 40)
        display_font_sm = ImageFont.truetype('Righteous-Regular.ttf', 20)
        display_font_xs = ImageFont.truetype('Righteous-Regular.ttf', 14)
        number_font = ImageFont.truetype('KellySlab-Regular.ttf', 24)
        image = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame
        draw = ImageDraw.Draw(image)
        # uptimes
        draw.text((5, 0), 'Uptime', font = display_font, fill = 0)
        x = 5
        y = 65
        for serv, ratio in uptimes.items():
            draw.text((x, y), serv, font = display_font_sm, fill = 0)
            y += 20
            draw.text((x+5, y), str(ratio) + "%", font = number_font, fill = 0)
            y += 26
        draw.line((0, 60, 150, 60), fill = 0, width = 3)
        draw.line((150, 0, 150, epd.height), fill = 0, width = 3)
        # down monitors, if none down, just don't show this section
        if len(down) > 0:
            draw.text((160, 0), 'Down Monitors', font = display_font, fill = 0)
            draw.line((150, 80, epd.width, 80), fill = 0, width = 3)
            draw.text((160, 50), ", ".join(down), font = display_font_sm, fill = 0)
            x = 160
            y = 210
        else:
            x = 160
            y = 0
        # backend events
        draw.text((x, y), 'Backend', font = display_font, fill = 0)
        draw.line((x-10, y+50, epd.width, y+50), fill = 0, width = 3)
        y = y + 60
        for event in backend_events:
            draw.text((x, y), f"({event['count']}) {event['title']}", font = display_font_xs, fill = 0)
            y += 20
            draw.text((x+8, y), event['culprit'], font = display_font_xs, fill = 0)
            y += 25
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
    #while True:
    uptimes = get_service_ratios()
    down = get_down_monitors()
    # frontend_events = get_sentry_events("frontend")
    backend_events = get_sentry_events("backend")
    display_test(uptimes, down, backend_events)
    #time.sleep(180) # 3 mins
    #     print(get_sentry_events("frontend"))
    #     print(get_sentry_events("backend"))
        # # print(get_cal_events(5))

if __name__ == "__main__":
    load_dotenv()
    main()
