qimport requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from pytz import timezone
from icalendar import Calendar, vText, Event
import json
import re

base_url = "https://www.portal.reinvent.awsevents.com/connect/"
favorites_url = "https://www.portal.reinvent.awsevents.com/connect/interests.ww"
login_url = "https://www.portal.reinvent.awsevents.com/connect/processLogin.do"
scheduling_url = "https://www.portal.reinvent.awsevents.com/connect/dwr/call/plaincall/ConnectAjax.getSchedulingJSON.dwr"
vegas = timezone("US/Pacific")

# Set username and password for reinvent event website
USERNAME = 'YOUR_USERNAME'
PASSWORD = 'YOUR_PASSWORD'

# login and start a session
session = requests.session()
payload = {"password": PASSWORD, "username": USERNAME }
resp = session.post(login_url, data=payload)

# get all the favorites
resp = session.get(favorites_url)
html = resp.content
soup = BeautifulSoup(html, "html.parser")

# find all selected sessions
selected_sessions = soup.findAll("div", {"class": "sessionRow"})

session_data = []

abbreviation_normalizer = re.compile("-R\d?")
abstract_cleaner = re.compile(".*>\n\n", re.DOTALL)

# loop through all sessions, and gather the needed information
for selected_session in selected_sessions:
    # get the link
    link = selected_session.find("a", {"class": "openInPopup"})
    url = link['href']

    # get the session title
    abbreviation = link.find("span", {"class": "abbreviation"}).text
    title = link.find("span", {"class": "title"}).text
    normalized_abbreviation = abbreviation_normalizer.sub("", abbreviation)

    # get the abstract
    abstract = selected_session.find("span", {"class": "abstract"}).text
    abstract = abstract_cleaner.sub("", abstract)
    session_url = "%s%s" % (base_url, url)

    # this contains the session id (int)
    session_id = url.split("=")[-1]

    # get my schedule status
    schedule_status = selected_session.find("span", {"class": "scheduleStatus"}).text.strip(' \t\n\r').split(" ")[-1]
    if len(schedule_status) > 0:
        schedule_status = "{" + schedule_status[0] + "} "
    else:
        schedule_status = ""

    # get the scheduling information and location from the magic json url
    payload = {
        "callCount":"1",
        "windowName":"",
        "c0-scriptName":"ConnectAjax",
        "c0-methodName":"getSchedulingJSON",
        "c0-id":"0",
        "c0-param0":"string:%s" % session_id,
        "batchId":"4",
        "instanceId":"0",
        "page":"%2Fconnect%2Finterests.ww",
        "scriptSessionId":"OGxWNAOpsVunFAFyWddX2cGpNYl/RTNxNYl-Roe8DFsEq",
    }
    resp = session.post(scheduling_url, data=payload)

    # do some magic and actually get the escaped json
    json_response = resp.content.split("\n")[5].replace('r.handleCallback("4","0","',"").replace('");',"").replace('\\"','"').replace("\\'","'")
    schedule_data = json.loads(json_response)['data'][0]
    print abbreviation + title


    # Friday, Dec 1, 9:15 AM
    # print schedule_data
    start_dt = datetime.strptime(schedule_data['startTime'], '%A, %b %d, %I:%M %p').replace(year=2017, tzinfo=vegas)
    schedule_data['startDatetime'] = start_dt
    end_dt = datetime.strptime(schedule_data['endTime'], '%I:%M %p').replace(day=start_dt.day, month=start_dt.month, year=2017, tzinfo=vegas)
    schedule_data['endDatetime'] = end_dt

    session_data.append({
        "abbreviation": abbreviation,
        "title": title,
        "abstract": abstract,
        "link": link,
        "schedule": schedule_data,
        "schedule_status": schedule_status,
        "normalized_abbreviation": normalized_abbreviation
    })

# avoid duplication
print ""

for session in session_data:
    for session2 in session_data:
        if session2 != session and session2['normalized_abbreviation'] == session['normalized_abbreviation']:
            if session2['schedule_status'] != "" and session2['schedule_status'] != "{O} " and session['schedule_status'] != "" and session['schedule_status'] != "{O} ":
                print "WARN: Multiple reservations for " + session['abbreviation'] + " / " + session2['abbreviation']
            elif session2['schedule_status'] == "" and session['schedule_status'] != "" and session['schedule_status'] != "{O} ":
                session2['schedule_status'] = "{O} "

# ok, we have everything we need, now generate an ical file
cal = Calendar()
cal.add('prodid', '-//Re-Invent plan generator product//mxm.dk//')
cal.add('version', '2.0')
for session in session_data:
    event = Event()
    event.add('summary', session['schedule_status'] + session['abbreviation'] + session['title'].replace("'","\'"))
    event.add('description', session['abstract'])
    event.add('location', session['schedule']['room'])
    event.add('dtstart', session['schedule']['startDatetime'])
    event.add('dtend', session['schedule']['endDatetime'])
    event.add('url', base_url + "/sessionDetail.ww?SESSION_ID=" + session['normalized_abbreviation'].replace(" - ", ""))
    event.add('dtstamp', session['schedule']['startDatetime'])
    cal.add_component(event)

# write the ical file
with open("reinvent.ics","w") as f:
    f.write(cal.to_ical())
