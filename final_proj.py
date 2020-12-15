from bs4 import BeautifulSoup
import requests
import json 
import time 
import sqlite3 
import re 
from flask import Flask, render_template, request
import plotly.graph_objects as go

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
PIXIV_IMAGES = 'https://www.pixiv.net/artworks/'

def write_animation_record(animation, conn, cur):
    """This function uses a soup to find the information about the animation and write the record to the database.

    Args:
        animation (soup): The soup for a part of the animation ranking page
        conn (sqlite connection): The connection to the database
        cur (sqlite cursur): The cursor of the database
    """
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
    score = soup.find('h4', class_='score')
    if score is not None:
        score = float(score.text.strip())
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
    """This function createa the animation table (if not exists yet) and uses a soup of the ranking page to create records for each animation

    Args:
        soup (soup): The soup for the whole animation ranking page on Bilibili
    """
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
    """This function uses requests to get an html page with cache 

    Args:
        Baseurl (str): The url of the page

    Returns:
        soup: The soup of the page
    """
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
    """This function uses the url of an animation detail page to get the description in the url and return the information about the animation in the database

    Args:
        url (str): The url of the animation detail page

    Returns:
        list: A list contains the information about the animation
    """
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
    title = result[0][0]
    score = result[0][5]
    play = result[0][1]
    danmuku = result[0][2]
    subscribe = result[0][3]
    episodes = result[0][4]
    description = soup.find('span', class_='absolute').text.strip()
    query = '''
    SELECT Ranking, Date FROM animation
    WHERE Url=?
    '''
    result = cur.execute(query, [url]).fetchall()
    conn.close()
    return [title, episodes, score, play, danmuku, subscribe, description, result]

def api_with_cache(keyword):
    """This function gets data using the Pixiv API with cache

    Args:
        keyword (str): The keyword to search on Pixiv

    Returns:
        dict: The dictionary of information gets from the Pixiv API
    """
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
    """This function writes the record of one image to the database.

    Args:
        image (dict): This dictionary of the image 
        conn (sqlite connection): The connection to the database
        cur (sqlite cursur): The cursur of the database
        keyword (str): The keyword used to search on Pixiv 
        count (int): The number of images about the keyword on Pixiv in the past one year
    """
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
    """This function writes the records of images about the keyword to the database

    Args:
        keyword (str): The keyword of the images

    Returns:
        int: a flag to show whether Pixiv API works today
    """
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
    flag = 1
    if images_info != False and 'response' in images_info.keys():
        images = images_info['response']
        count = images_info['pagination']['total']
        for image in images:
            write_image_record(image, conn, cur, keyword, count)
        flag = 0
    conn.close()
    return flag 

def images_for_date(date):
    """This function do the seaching and writing images records for every animation on the ranking list

    Args:
        date ([type]): [description]
    """
    query = '''
    SELECT Name FROM animation
    WHERE Date=?
    '''
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    keywords = cur.execute(query, [date]).fetchall()
    for keyword in keywords:
        flag = dbwrite_image(keyword[0])
        if flag == 1:
            break 
    conn.close()

def fetch_daily_data():
    """This function get data from the ranking page, write the records for animations, and search and write the records for images. For the first time in a day, it will get data from internet. Then, it will use cache.
    """
    soup = read_with_cache(RANKING_BASEURL)
    dbwrite_animation(soup)
    images_for_date(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10])

def get_ranking_data():
    """This function gets the ranking information today from the database.

    Returns:
        list: A list of animation and ranking tuples
    """
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    query = '''
    SELECT Ranking, Name FROM animation
    WHERE Date = ?
    '''
    date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]
    results = cur.execute(query, [date]).fetchall()
    conn.close()
    return results

def detail_information_format(ranking):
    """This function gets data for the animation detail information page from the database and return a plotly graph

    Args:
        ranking (int): The ranking of the animation

    Returns:
        list: A list of the animation information and the plotly graph
    """
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    query = '''
    SELECT Url
    FROM animation
    WHERE Ranking=? AND Date=?
    '''
    query_blank = [ranking, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]]
    result = cur.execute(query, query_blank).fetchall()
    conn.close()
    results = print_animation_detail_information(result[0][0])
    x_vals = []
    y_vals = []
    for record in results[7]:
        y_vals.append(record[0])
        x_vals.append(record[1])
    data = go.Line(
        x = x_vals, 
        y = y_vals
    )
    fig = go.Figure(data=data)
    div = fig.to_html(full_html=False)
    return [results, div]

def generate_ranking_plot():
    """This function generate a ranking plot about the title and the ranking score for the animations on the ranking page today

    Returns:
        plotly graph: A plotly graph about the ranking scores
    """
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    query = '''
    SELECT Name, Ranking_score
    FROM animation
    WHERE Date=?
    '''
    query_blank = [time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]]
    result = cur.execute(query, query_blank).fetchall()
    conn.close()
    x_vals = []
    y_vals = []
    for record in result:
        y_vals.append(record[1])
        x_vals.append(record[0])
    data = go.Line(
        x = x_vals, 
        y = y_vals
    )
    fig = go.Figure(data=data)
    div = fig.to_html(full_html=False)
    return div 

def get_Pixiv_images(ranking):
    """This function returns the records about images regarding a specific animation from the database

    Args:
        ranking (int): The ranking about the animation

    Returns:
        list: A list of the records of images and the title of the animation
    """
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    query = '''
    SELECT Name
    FROM animation
    WHERE Ranking=? AND Date=?
    '''
    query_blank = [ranking, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]]
    result = cur.execute(query, query_blank).fetchall()
    conn.close()
    title = result[0][0]
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    query = '''
    SELECT Id, Title, View, Favorite, Author_name, Author_id, Caption, Image_id
    FROM image
    WHERE Animation=?
    '''
    query_blank = [title]
    result = cur.execute(query, query_blank).fetchall()
    conn.close()
    return [result, title]

def generate_ranking_images_plot():
    """This function generates a graph about the ranking on Bilibili and number of images on Pixiv

    Returns:
        plotly graph: A scatter plot about the ranking and number of images
    """
    conn = sqlite3.connect(DB_FILE_NAME)
    cur = conn.cursor()
    query = '''
    SELECT Ranking, Image_count
    FROM animation
    JOIN image ON animation.Name = image.Animation
    WHERE Date=?
    '''
    query_blank = [time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())[0:10]]
    result_animation = cur.execute(query, query_blank).fetchall()
    x_vals = []
    y_vals = []
    for record in result_animation:
        x_vals.append(record[0])
        y_vals.append(record[1])
    conn.close()
    data = go.Scatter(
        x = x_vals, 
        y = y_vals
    )
    fig = go.Figure(data=data)
    div = fig.to_html(full_html=False)
    return div 

app = Flask(__name__)

@app.route('/')
def index():
    results = get_ranking_data()
    return render_template('index.html', results=results)

@app.route('/ranking_plot')
def ranking_plot():
    results = generate_ranking_plot()
    return render_template('ranking_plot.html', plot_div=results)

@app.route('/ranking_vs_images')
def ranking_vs_images():
    results = generate_ranking_images_plot()
    return render_template('ranking_plot.html', plot_div=results)

@app.route('/Pixiv_images', methods=['POST'])
def Pixiv_images():
    ranking = request.form["ranking_2"]
    results = get_Pixiv_images(ranking)
    return render_template('Pixiv_images.html',results=results[0], Title=results[1])

@app.route('/handle_form', methods=['POST'])
def handle_the_form():
    ranking = request.form["ranking"]
    results = detail_information_format(ranking)
    return render_template('detail_information.html',result=results[0], plot_div=results[1])

if __name__ == '__main__':
    fetch_daily_data()
    app.run(debug=True)
