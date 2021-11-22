from django.http import HttpResponse
from django.shortcuts import render
import cloudscraper
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import re
import os
import time


def download(link):
    # Adding Browser / User-Agent Filtering should help ie.
    # will give you only desktop firefox User-Agents on Windows
    scraper = cloudscraper.create_scraper(browser={'browser': 'firefox','platform': 'windows','mobile': False})

    html = scraper.get(link).content

    name = re.search("manga/(.*?)/", link).group(1)
    soup = BeautifulSoup(html, 'html.parser')
    img_list = []
    for noscript in soup.find_all("noscript"):
        img = noscript.find("img")
        if not img: continue

        link = img["src"]
        img_list.append(Image.open(BytesIO(scraper.get(link, headers={'referer': "https://hentaicube.net/"}).content)))

    pdf_filename = "{}.pdf".format(name)
    img_list[0].save(pdf_filename, "PDF", resolution=300.0, save_all=True, append_images=img_list[1:])
    return pdf_filename


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