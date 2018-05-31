#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from datetime import datetime
from time import sleep
from typing import Generator, List, NoReturn, Tuple
from xml.etree import ElementTree

import requests
import tomd
from bs4 import BeautifulSoup
from html2text import html2text


def get_post(html: str) -> Tuple[str, str, Tuple[str], datetime]:
    soup = BeautifulSoup(html, 'lxml')
    article = soup.find('article')

    if not article:
        raise ValueError('Not found article element')
    info = article.find('div', {'class': 'titleWrap'})
    if not info:
        raise ValueError('Not found div elements with class titleWrap')

    title = info.find('a').get_text()
    categories_text = info.find('span', {'class': 'category'}).get_text()
    categories = tuple(categories_text.strip().split('/'))
    date_text = info.find('span', {'class': 'date'}).get_text()
    date = datetime.strptime(date_text.strip(), '%Y.%m.%d %H:%M')
    info.decompose()

    postbtn = article.find('div', {'class': 'container_postbtn'})
    related = article.find('div', {'class': 'relatedWrap'})
    author = article.find('div', {'class': 'author'})
    if postbtn:
        postbtn.decompose()
    if related:
        related.decompose()
    if author:
        author.decompose()

    post = html2text(tomd.convert(article.prettify()))
    return post, title, categories, date


def next_post(sess: requests.Session, base: str) \
        -> Generator[Tuple[str, str, Tuple[str], datetime], None, None]:
    rlink = f'{base}/rss'
    with sess.get(rlink) as resp:
        rss = ElementTree.fromstring(resp.text)
        plink_last = rss.find('channel').find('item').find('link').text
        entry_id_last = int(plink_last.split('/')[-1])

    for entry_id in range(1, entry_id_last + 1):
        plink = f'{base}/{entry_id}'
        with sess.get(plink) as resp:
            try:
                yield get_post(resp.text)
            except ValueError as e:
                print(f'[!] {e}', file=sys.stderr)
        sleep(1)


def main(argv: Tuple[str]) -> None:
    if len(argv) != 2:
        help()

    scheme = 'http'
    host = argv[1]
    base = f'{scheme}://{host}'
    ua = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) ' \
         'Chrome/60.0.3112.113 Whale/1.0.41.8 Safari/537.36'

    with requests.session() as sess:
        sess.headers.update({'user-agent': ua})
        for post, title, categories, date in next_post(sess, base):
            print(title, categories, date)
            print(post)


def help() -> NoReturn:
    msg = f'usage: python3 {__file__} <tistory blog host>'
    sys.exit(msg)


if __name__ == '__main__':
    main(tuple(sys.argv))
