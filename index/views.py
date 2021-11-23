from django.http import HttpResponse
from django.shortcuts import render
import cloudscraper
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import re
import os
import time
from threading import Thread


def download(link):
    # Adding Browser / User-Agent Filtering should help ie.
    # will give you only desktop firefox User-Agents on Windows
    scraper = cloudscraper.create_scraper(browser={'browser': 'firefox','platform': 'windows','mobile': False})
    name = re.search("manga/(.*?)/", link).group(1)
    try:
        chapter = re.search("manga/.*?/(.*?)/", link).group(1)
    except:
        chapter = None

    if chapter:
        # single download
        img_list = [[]]
        crawl_chapter(scraper, link, img_list, 0)
    else:
        # multi download
        html = scraper.get(link).content
        soup = BeautifulSoup(html, 'html.parser')
        chapters = soup.find_all("li", {"class": "wp-manga-chapter"})
        img_list = [[] for _ in range(len(chapters))]
        threads = []
        for index, chap in enumerate(chapters[::-1]):
            link = chap.find('a')['href']
            process = Thread(target=crawl_chapter, args=[scraper, link, img_list, index])
            process.start()
            threads.append(process)
        for process in threads:
            process.join()

    img_list_flatten = [item for sublist in img_list for item in sublist]
    pdf_filename = "{}-{}.pdf".format(name, chapter if chapter else "%schaps" % len(chapters))
    img_list_flatten[0].save(pdf_filename, "PDF", resolution=300.0, save_all=True, append_images=img_list_flatten[1:])
    return pdf_filename


def crawl_chapter(scraper, link, img_list, index):
    html = scraper.get(link).content
    soup = BeautifulSoup(html, 'html.parser')
    for noscript in soup.find_all("noscript"):
        img = noscript.find("img")
        if not img: continue

        link = img["src"]
        img_list[index].append(
            Image.open(BytesIO(scraper.get(link, headers={'referer': "https://hentaicube.net/"}).content)))


# Create your views here.
def index(request):
    if request.method == "POST":
        pdf_filename = download(request.POST['link'])
        with open(pdf_filename, 'rb') as file:
            response = HttpResponse(file.read(), content_type="application/pdf")
            response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdf_filename)
        time.sleep(1)
        os.remove(pdf_filename)
        return response
    else:
        return render(request, 'index/index.html')