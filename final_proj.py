from bs4 import BeautifulSoup
import requests
import webbrowser
import json 
import time 
import sqlite3 
import re 

CACHE_FILE_NAME = 'cache.json'
DB_FILE_NAME = 'final_proj_db.sqlite'
RANKING_BASEURL = 'https://www.bilibili.com/v/popular/rank/bangumi'
PIXIV_BASEURL = 'https://api.imjad.cn/pixiv/v1/'
INSERT_ANIMATION = '''
    INSERT INTO animation
    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
'''
INSERT_IMAGE = '''
    INSERT INTO image
    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
'''

def write_animation_record(animation, conn, cur):
    url = 'https:' + animation.find('a', class_='title').get('href').strip()
    name = animation.find('a', class_='title').text.strip()
    ranking = animation.find('div', class_='num').text.strip()
    date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]
    data = animation.find_all('div', class_='detail')[0].text.split(" ")
    while '' in data:
        data.remove('')
    while '\n' in data:
        data.remove('\n')
    data_new = []
    for value in data:
        if '亿' in value:
            data_new.append(int(float(value[:-2]) * 100000000))
        else:
            data_new.append(int(float(value[:-2]) * 10000))
    play = data_new[0]
    danmaku = data_new[1]
    subscribe = data_new[2]
    episode = animation.find('div', class_='pgc-info').text.strip()
    episode = re.sub("\D", "", episode)
    ranking_score = animation.find('div', class_='pts').text.strip()
    ranking_score = re.sub("\D", "", ranking_score)
    soup = read_with_cache(url)
    score = float(soup.find('h4', class_='score').text.strip())
    animation_record = [url, name, ranking, date, play, danmaku, subscribe, episode, ranking_score, score]
    animation_test = [url, date]
    animation_exist_test = '''
    SELECT Url, Date FROM animation
    WHERE Url=? AND Date=?
    '''
    result = cur.execute(animation_exist_test,animation_test).fetchall()
    if result == []:
        cur.execute(INSERT_ANIMATION, animation_record)
    conn.commit()

def dbwrite_animation(soup):
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    create_animation_table = '''
        CREATE TABLE IF NOT EXISTS "animation" (
	        "Id"	INTEGER NOT NULL UNIQUE,
	        "Url"	TEXT NOT NULL,
	        "Name"	TEXT NOT NULL,
	        "Ranking"	INTEGER NOT NULL,
	        "Date"	INTEGER NOT NULL,
	        "Play"	INTEGER NOT NULL,
	        "Danmaku"	INTEGER NOT NULL,
	        "Subscribe"	INTEGER NOT NULL,
	        "Episode"	INTEGER NOT NULL,
	        "Ranking_score"	INTEGER NOT NULL,
	        "Score"	INTEGER,
	        PRIMARY KEY("Id" AUTOINCREMENT)
        );
    '''
    cur.execute(create_animation_table)
    conn.commit()
    animations = soup.find_all('li',class_='rank-item')
    for animation in animations:
        write_animation_record(animation, conn, cur)
    conn.close()

def read_with_cache(Baseurl):
    urltag = Baseurl+time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]
    try:
        cache_file = open(CACHE_FILE_NAME, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        cache_file.close()
    except:
        cache_dict = {}
    if (urltag) in cache_dict.keys():
        soup = BeautifulSoup(cache_dict[urltag], 'html.parser')
        print("Using cache", Baseurl)
    else:
        response = requests.get(Baseurl)
        soup = BeautifulSoup(response.text, 'html.parser')
        cache_dict[urltag] = response.text
        print("Fetching", Baseurl)
        cache_file = open(CACHE_FILE_NAME, 'w')
        dumped_cache_dict = json.dumps(cache_dict)
        cache_file.write(dumped_cache_dict)
        cache_file.close()
    return soup 

def print_animation_detail_information(url):
    urltag = url+time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]
    cache_file = open(CACHE_FILE_NAME, 'r')
    cache_contents = cache_file.read()
    cache_dict = json.loads(cache_contents)
    cache_file.close()
    soup = BeautifulSoup(cache_dict[urltag], 'html.parser')
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    query = '''
    SELECT Name, Play, Danmaku, Subscribe, Episode, Score
    FROM animation
    WHERE Url=? AND Date=?
    '''
    query_blank = [url, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]]
    result = cur.execute(query, query_blank).fetchall()
    print('Animation Title: ', result[0][0])
    print("Score: ", result[0][5], " (Out of 10)")
    print('Detail Description')
    description = soup.find('span', class_='absolute').text.strip()
    print(description)
    print("Play volumn:      ", result[0][1])
    print("Danmaku number:   ", result[0][2])
    print("Subscribe number: ", result[0][3])
    print(result[0][4], "episode(s) for now. ")
    conn.close()
    return

def api_with_cache(keyword):
    urltag = PIXIV_BASEURL + keyword + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]
    try:
        cache_file = open(CACHE_FILE_NAME, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        cache_file.close()
    except:
        cache_dict = {}
    if urltag in cache_dict.keys():
        dict_result = json.loads(cache_dict[urltag])
        print("Using cache", keyword)
    else:
        params = {
            'type':'search',
            'word':keyword,
            'mode':'tag',
            'order':'desc',
            'period':'year',
            'page':1,
            'per_page':30
        } 
        response = requests.get(PIXIV_BASEURL, params=params)
        dict_result = response.json()
        cache_dict[urltag] = response.text
        print("Fetching", keyword)
        cache_file = open(CACHE_FILE_NAME, 'w')
        dumped_cache_dict = json.dumps(cache_dict)
        cache_file.write(dumped_cache_dict)
        cache_file.close()
    return dict_result

def write_image_record(image, conn, cur, keyword, count):
    image_id = image['id']
    title = image['title']
    caption = image['caption']
    view = image['stats']['views_count']
    favorite = image['stats']['favorited_count']['public'] + image['stats']['favorited_count']['private']
    time = image['created_time']
    author_name = image['user']['name']
    author_id = image['user']['id']
    animation = keyword
    image_count =  count
    image_record = [image_id, title, caption, view, favorite, time, author_name, author_id, animation, image_count]
    image_exist_test = '''
    SELECT Image_id FROM image
    WHERE Image_id=?
    '''
    result = cur.execute(image_exist_test, [image_id]).fetchall()
    if result == []:
        cur.execute(INSERT_IMAGE, image_record)
    conn.commit()

def dbwrite_image(keyword):
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    create_image_table = '''
        CREATE TABLE IF NOT EXISTS "image" (
	        "Id"	INTEGER NOT NULL UNIQUE,
	        "Image_id"	INTEGER NOT NULL,
	        "Title"	TEXT NOT NULL,
	        "Caption"	TEXT,
	        "View"	INTEGER NOT NULL,
	        "Favorite"	INTEGER NOT NULL,
	        "Time"	TEXT NOT NULL,
	        "Author_name"	TEXT NOT NULL,
	        "Author_id"	INTEGER NOT NULL,
	        "Animation"	TEXT,
	        "Image_count"	INTEGER,
	        PRIMARY KEY("Id" AUTOINCREMENT)
        );
    '''
    cur.execute(create_image_table)
    conn.commit()
    images_info = api_with_cache(keyword)
    images = images_info['response']
    count = images_info['pagination']['total']
    for image in images:
        write_image_record(image, conn, cur, keyword, count)
    conn.close()

def images_for_date(date):
    query = '''
    SELECT Name FROM animation
    WHERE Date=?
    '''
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    keywords = cur.execute(query, [date]).fetchall()
    for keyword in keywords:
        dbwrite_image(keyword[0])
    conn.close()

def fetch_daily_data():
    soup = read_with_cache(RANKING_BASEURL)
    dbwrite_animation(soup)
    images_for_date('2020-11-30')

'''
print_animation_detail_information('https://www.bilibili.com/bangumi/play/ss25739')
'''

fetch_daily_data()

'''
webbrowser.open_new('https://www.pixiv.net/artworks/'+'85603266')
'''
