#!/usr/bin/python3

import praw
import os
import logging.handlers
from lxml import html
import requests
import datetime
import time
import sys
import traceback
import json
import configparser
import re

### Config ###
LOG_FOLDER_NAME = "logs"
SUBREDDIT = "SoundersFC"
SUBREDDIT_TEAMS = "mls"
USER_AGENT = "SoundersSideBarUpdater (by /u/Watchful1)"
TEAM_NAME = "Seattle Sounders FC"

### Logging setup ###
LOG_LEVEL = logging.DEBUG
if not os.path.exists(LOG_FOLDER_NAME):
    os.makedirs(LOG_FOLDER_NAME)
LOG_FILENAME = LOG_FOLDER_NAME+"/"+"bot.log"
LOG_FILE_BACKUPCOUNT = 5
LOG_FILE_MAXSIZE = 1024 * 256

log = logging.getLogger("bot")
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
log_stderrHandler = logging.StreamHandler()
log_stderrHandler.setFormatter(log_formatter)
log.addHandler(log_stderrHandler)
if LOG_FILENAME is not None:
	log_fileHandler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=LOG_FILE_MAXSIZE, backupCount=LOG_FILE_BACKUPCOUNT)
	log_formatter_file = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	log_fileHandler.setFormatter(log_formatter_file)
	log.addHandler(log_fileHandler)

comps = [{'name': 'MLS', 'link': '/MLS', 'acronym': 'MLS'}
	,{'name': 'Preseason', 'link': '/MLS', 'acronym': 'UNK'}
	,{'name': 'CONCACAF', 'link': 'http://category/champions-league/schedule-results', 'acronym': 'CCL'}
	,{'name': 'Open Cup', 'link': '/MLS', 'acronym': 'OPC'}
]


def getCompLink(compName):
	for comp in comps:
		if comp['name'] in compName:
			return comp['link']

	return ""


def matchesTable(table, str):
	for item in table:
		if str in item:
			return True
	return False


teams = [{'link': '/r/dynamo', 'contains': 'Houston Dynamo'}
	,{'link': '/SEA', 'contains': 'Seattle Sounders FC'}
	,{'link': '/r/SportingKC', 'contains': 'Sporting Kansas City'}
	,{'link': '/r/fcdallas', 'contains': 'FC Dallas'}
	,{'link': '/r/timbers', 'contains': 'Portland Timbers'}
	,{'link': '/r/SJEarthquakes', 'contains': 'San Jose Earthquakes'}
	,{'link': '/r/whitecapsfc', 'contains': 'Vancouver Whitecaps FC'}
	,{'link': '/r/realsaltlake', 'contains': 'Real Salt Lake'}
	,{'link': '/r/LAGalaxy', 'contains': 'LA Galaxy'}
	,{'link': '/r/Rapids', 'contains': 'Colorado Rapids'}
	,{'link': '/r/minnesotaunited', 'contains': 'Minnesota United'}
	,{'link': '/r/LAFC', 'contains': 'Los Angeles Football Club'}
	,{'link': '/r/FCCincinnati', 'contains': 'FC Cincinnati'}
]


def getTeamLink(name):
	for item in teams:
		if item['contains'].lower() in name.lower():
			return '[](' + item['link'] + ') ' + name

	return ""


### Parse table ###
def compareTeams(team1, team2):
	if int(team1['points']) > int(team2['points']):
		return True
	elif int(team1['points']) < int(team2['points']):
		return False
	else:
		if int(team1['wins']) > int(team2['wins']):
			return True
		elif int(team1['wins']) < int(team2['wins']):
			return False
		else:
			if int(team1['goalDiff']) > int(team2['goalDiff']):
				return True
			elif int(team1['goalDiff']) < int(team2['goalDiff']):
				return False
			else:
				if int(team1['goalsFor']) > int(team2['goalsFor']):
					return True
				elif int(team1['goalsFor']) < int(team2['goalsFor']):
					return False
				else:
					log.error("Ran out of tiebreakers")
					return True


def parseTable():
	page = requests.get("https://www.mlssoccer.com/standings")
	tree = html.fromstring(page.content)

	firstConf = {'name': "E", 'size': 12}
	secondConf = {'name': "W", 'size': 12}
	standings = []
	for i in range(0, firstConf['size']+secondConf['size']):
		standings.append({'conf': (firstConf['name'] if i < firstConf['size'] else secondConf['name'])})

	elements = [{'title': 'Points', 'name': 'points'}
		,{'title': 'Games Played', 'name': 'played'}
		,{'title': 'Goals For', 'name': 'goalsFor'}
		,{'title': 'Goal Difference', 'name': 'goalDiff'}
		,{'title': 'Wins', 'name': 'wins'}
		,{'title': 'Losses', 'name': 'losses'}
		,{'title': 'Ties', 'name': 'ties'}
	]

	for element in elements:
		for i, item in enumerate(tree.xpath("//td[@data-title='"+element['title']+"']/text()")):
			standings[i][element['name']] = item

	for i, item in enumerate(tree.xpath("//td[@data-title='Club']")):
		names = item.xpath(".//a/span/text()")
		if not len(names):
			log.warning("Couldn't find team name")
			continue
		teamName = ""
		for name in names:
			if len(name) > len(teamName):
				teamName = name

		standings[i]['name'] = name


	sortedStandings = []
	firstCount = 0
	secondCount = firstConf['size']
	while True:
		if compareTeams(standings[firstCount], standings[secondCount]):
			standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
			sortedStandings.append(standings[firstCount])
			firstCount += 1
		else:
			standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
			sortedStandings.append(standings[secondCount])
			secondCount += 1

		if firstCount == firstConf['size']:
			while True:
				standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
				sortedStandings.append(standings[secondCount])
				secondCount += 1

				if secondCount == firstConf['size'] + secondConf['size']:
					break

			break

		if secondCount == firstConf['size'] + secondConf['size']:
			while True:
				standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
				sortedStandings.append(standings[firstCount])
				firstCount += 1

				if firstCount == firstConf['size']:
					break

			break

	return sortedStandings


def parseSchedule():
	page = requests.get("https://www.soundersfc.com/schedule?year=2019")
	tree = html.fromstring(page.content)

	schedule = []
	date = ""
	for i, element in enumerate(tree.xpath("//ul[contains(@class,'schedule_list')]/li[contains(@class,'row')]")):
		match = {}
		dateElement = element.xpath(".//div[contains(@class,'match_date')]/text()")
		if not len(dateElement):
			log.warning("Couldn't find date for match, skipping")
			continue

		timeElement = element.xpath(".//span[contains(@class,'match_time')]/text()")
		if not len(timeElement):
			log.warning("Couldn't find time for match, skipping")
			continue

		if 'TBD' in timeElement[0]:
			match['datetime'] = datetime.datetime.strptime(dateElement[0].strip(), "%A, %B %d, %Y")
			match['status'] = 'tbd'
		else:
			match['datetime'] = datetime.datetime.strptime(dateElement[0] + timeElement[0], "%A, %B %d, %Y %I:%M%p PT")
			match['status'] = ''

		statusElement = element.xpath(".//span[contains(@class,'match_result')]/text()")
		if len(statusElement):
			match['scoreString'] = statusElement[0].replace('IN', '').replace('OSS', '').replace('RAW', '')
			match['status'] = 'final'
			homeScores = re.findall('(\d+).*-', statusElement[0])
			if len(homeScores):
				match['homeScore'] = homeScores[0]
			else:
				match['homeScore'] = -1

			awayScores = re.findall('-.*(\d+)', statusElement[0])
			if len(awayScores):
				match['awayScore'] = awayScores[0]
			else:
				match['awayScore'] = -1
		else:
			match['status'] = ''
			match['homeScore'] = -1
			match['awayScore'] = -1

		opponentElement = element.xpath(".//div[contains(@class,'match_matchup')]/text()")
		homeAwayElement = element.xpath(".//span[contains(@class,'match_home_away')]/text()")

		if not len(opponentElement) or not len(homeAwayElement):
			log.debug("Could not find any opponent")
			continue

		if homeAwayElement[0] == 'H':
			match['home'] = TEAM_NAME
			match['away'] = opponentElement[0].title()
		elif homeAwayElement[0] == 'A':
			match['home'] = opponentElement[0][3:].title()
			match['away'] = TEAM_NAME
		else:
			log.debug("Could not find opponent")
			continue

		compElement = element.xpath(".//span[contains(@class,'match_competition ')]/text()")
		if len(compElement):
			match['comp'] = compElement[0]
		else:
			match['comp'] = ""

		tvElement = element.xpath(".//div[@class='match_info']/text()")
		if len(tvElement):
			match['tv'] = tvElement[0][0:tvElement[0].find(',')].replace('\n','')
		else:
			match['tv'] = ""

		schedule.append(match)

	return schedule


log.debug("Connecting to reddit")

once = False
debug = False
user = None
if len(sys.argv) >= 2:
	user = sys.argv[1]
	for arg in sys.argv:
		if arg == 'once':
			once = True
		elif arg == 'debug':
			debug = True
else:
	log.error("No user specified, aborting")
	sys.exit(0)


try:
	r = praw.Reddit(
		user
		,user_agent=USER_AGENT)
except configparser.NoSectionError:
	log.error("User "+user+" not in praw.ini, aborting")
	sys.exit(0)

while True:
	startTime = time.perf_counter()
	log.debug("Starting run")

	strListGames = []
	strListTable = []
	skip = False

	schedule = []
	standings = []
	try:
		schedule = parseSchedule()
		standings = parseTable()
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		skip = True

	try:
		teamGames = []
		nextGameIndex = -1
		lastRecentIndex = 0
		for game in schedule:
			if game['home'] == TEAM_NAME or game['away'] == TEAM_NAME:
				teamGames.append(game)
				if game['datetime'] + datetime.timedelta(hours=2) > datetime.datetime.now() and nextGameIndex == -1:
					nextGameIndex = len(teamGames) - 1

		strListGames.append("##Recent Match Results\n\n")
		strListGames.append("Date|||Opponent|Result\n")
		strListGames.append(":---:|:---:|---|:---|:---:|:---:\n")

		lastRecentIndex = 0 if (nextGameIndex - 9 < 0) else nextGameIndex - 9

		for game in teamGames[lastRecentIndex:nextGameIndex]:
			strListGames.append(game['datetime'].strftime("%m/%d"))
			strListGames.append("|[](")
			strListGames.append(getCompLink(game['comp']))
			strListGames.append(")|")
			if game['home'] == TEAM_NAME:
				strListGames.append("H")
				strListGames.append("|")
				strListGames.append(game['away'])
			else:
				strListGames.append("A")
				strListGames.append("|")
				strListGames.append(game['home'])
			strListGames.append("|[")
			strListGames.append(game['scoreString'])
			strListGames.append("]")
			strListGames.append("\n")

		strListGames.append("##Upcoming Matches\n\n")
		strListGames.append("Date|||Opponent|PDT|Watch\n")
		strListGames.append(":---:|:---:|---|---|---|:---\n")
		for game in teamGames[nextGameIndex:nextGameIndex+6]:
			strListGames.append(game['datetime'].strftime("%m/%d"))
			strListGames.append("|")
			strListGames.append("[](")
			strListGames.append(getCompLink(game['comp']))
			strListGames.append(")|")
			if game['home'] == TEAM_NAME:
				strListGames.append("H|")
				strListGames.append(game['away'])
			else:
				strListGames.append("A|")
				strListGames.append(game['home'])
			strListGames.append("|")
			if game['status'] == 'tbd':
				strListGames.append("TBD")
			else:
				strListGames.append(game['datetime'].strftime("%I:%M %p"))
			strListGames.append("|")
			strListGames.append(game['tv'])
			strListGames.append("\n")

		strListGames.append("\n\n")


	except Exception as err:
		log.warning("Exception parsing table")
		log.warning(traceback.format_exc())
		skip = True

	try:
		strListTable.append("##2018 Western Conference Standings\n\n")
		strListTable.append("Club|Pts|GP|W|L|D|GD\n")
		strListTable.append(":---|:---:|:---:|:---:|:---:|:---:|:---:\n")

		for team in standings:
			if team['conf'] != 'W':
				continue
			strListTable.append(getTeamLink(team['name']))
			strListTable.append(" | ")
			strListTable.append(team['points'])
			strListTable.append(" | ")
			strListTable.append(team['played'])
			strListTable.append(" | ")
			strListTable.append(team['wins'])
			strListTable.append(" | ")
			strListTable.append(team['losses'])
			strListTable.append(" | ")
			strListTable.append(team['ties'])
			strListTable.append(" | ")
			strListTable.append(team['goalDiff'])
			strListTable.append(" |\n")

		strListTable.append("\n\n\n")
	except Exception as err:
		log.warning("Exception parsing table")
		log.warning(traceback.format_exc())
		skip = True

	if not skip:
		try:
			subreddit = r.subreddit(SUBREDDIT)
			description = subreddit.description
			begin = description[0:description.find("##Recent Match Results")]
			mid = description[description.find("##S2 Matches"):description.find("##2018 Western Conference Standings")]
			end = description[description.find("##2018 Top Goal Scorers "):]

			if debug:
				log.info(begin + ''.join(strListGames) +mid + ''.join(strListTable) + end)
			else:
				try:
					subreddit.mod.update(description=begin + ''.join(strListGames) +mid + ''.join(strListTable) + end)
				except Exception as err:
					log.warning("Exception updating sidebar")
					log.warning(traceback.format_exc())
		except Exception as err:
			log.warning("Broken sidebar")
			log.warning(traceback.format_exc())
			skip = True

	log.debug("Run complete after: %d", int(time.perf_counter() - startTime))
	if once:
		break
	time.sleep(15 * 60)
