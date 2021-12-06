from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse
from django.shortcuts import render
import cloudscraper
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import re
import time
from threading import Thread
import gc
from queue import Queue
import base64
import os
from django.views.decorators.csrf import csrf_exempt


def stream_generator(queue_stream):
    while queue_stream.empty():
        time.sleep(5)
        print('slept 5')
        yield ' '  # whitespace because base64 ignores, easily trim
    pdf_base64 = queue_stream.get()
    print('got base64')
    yield pdf_base64
    time.sleep(1)
    pdf_filename = queue_stream.get()
    print('got name')
    yield pdf_filename


def download(link, queue_stream):
    # Adding Browser / User-Agent Filtering should help ie.
    # will give you only desktop firefox User-Agents on Windows
    scraper = cloudscraper.create_scraper(browser={'browser': 'firefox','platform': 'windows','mobile': False})
    site = re.search("/{0,2}([a-zA-Z0-9.]*?)/", link).group(1)

    if site.startswith("hentaicube"):
        name = re.search("manga/(.*?)/", link).group(1)
        try:
            chapter = re.search("manga/.*?/(.*?)/", link).group(1)
        except:
            chapter = None
    elif site.startswith("hentaivn"):
        try:
            # single
            name = re.search("xem-truyen-(.*?).html", link).group(1)
            chapter = re.search("oneshot", link)
            if not chapter:
                chapter = re.search("(chap-.*?).html", link).group(1)
            else:
                chapter = "oneshot"
            name = name.replace("-{}".format(chapter), "")
        except:
            # multi
            name = re.search("doc-truyen-(.*?).html", link).group(1)
            chapter = None

    if chapter:
        # single download
        img_list = [[]]
        crawl_chapter(scraper, link, img_list, 0, site)
    else:
        # multi download
        html = scraper.get(link).content
        soup = BeautifulSoup(html, 'html.parser')
        if site.startswith("hentaicube"):
            chapters = soup.find_all("li", {"class": "wp-manga-chapter"})
        elif site.startswith("hentaivn"):
            chapters = soup.select("td:first-child")

        del html
        del soup
        gc.collect()
        img_list = [[] for _ in range(len(chapters))]
        threads = []
        for index, chap in enumerate(chapters[::-1]):
            link = chap.find('a')['href']
            process = Thread(target=crawl_chapter, args=[scraper, link, img_list, index, site])
            process.start()
            threads.append(process)
        for process in threads:
            process.join()

    img_list_flatten = [item for sublist in img_list for item in sublist]
    del img_list
    gc.collect()
    pdf_filename = "{}-{}.pdf".format(name, chapter if chapter else "%schaps" % len(chapters))
    # img_list_flatten[0].save(pdf_filename, "PDF", resolution=200.0, save_all=True, append_images=img_list_flatten[1:])
    img_list_flatten[0].save(pdf_filename, "PDF", resolution=200.0)
    img_list_flatten[0].close()
    for i in range(1, len(img_list_flatten), 50):
        print(i)
        img_list_flatten[i].save(pdf_filename, "PDF", resolution=200.0, save_all=True,
                                 append_images=img_list_flatten[i+1:i+50], append=True)
        for img in img_list_flatten[i:i+50]:
            img.close()
        time.sleep(1)
    del img_list_flatten
    gc.collect()
    print('after delete flatten')
    with open(pdf_filename, "rb") as pdf_file:
        queue_stream.put(base64.b64encode(pdf_file.read()))
    queue_stream.put(" " + pdf_filename)
    os.remove(pdf_filename)


def crawl_chapter(scraper, link, img_list, index, site):
    print("crawling", index)
    if not link.startswith("http"):
        link = "https://{}".format(site) + link
    html = scraper.get(link).content
    soup = BeautifulSoup(html, 'html.parser')
    if site.startswith("hentaicube"):
        imgs = soup.find("div", {"class": "text-left"}).find("div").find_all("img")
    elif site.startswith("hentaivn"):
        imgs = soup.find("div", {"id": "image"}).find_all("img")
    referer = "https://{}/".format(site)

    del html
    del soup
    gc.collect()
    for img in imgs:
        link = img["src"]
        # print(link)
        img_list[index].append(
            Image.open(BytesIO(scraper.get(link, headers={'referer': referer}).content)).convert("RGB"))
    print("done", index)


# Create your views here.
@csrf_exempt
def index(request):
    if request.method == "POST":
        queue_stream = Queue()
        _ = request.body
        download_process = Thread(target=download, args=[request.POST['link'], queue_stream])
        download_process.start()
        response = StreamingHttpResponse(stream_generator(queue_stream), status=200, content_type='text/event-stream')
        return response

        # pdf_filename = download(request.POST['link'])
        # with open(pdf_filename, 'rb') as file:
        #     response = HttpResponse(file.read(), content_type="application/pdf")
        #     response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdf_filename)
        # time.sleep(1)
        # os.remove(pdf_filename)
        # return response
    else:
        return render(request, 'index/index.html')
