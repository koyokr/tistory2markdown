#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import typing

import requests
from bs4 import BeautifulSoup, SoupStrainer
from html2text import html2text


def main(argv: typing.Iterable) -> None:
    if len(argv) != 2:
        help()
    scheme = 'http'
    host = argv[1]
    base = f'{scheme}://{host}'

    article_strainer = SoupStrainer('article')
    ua = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) ' \
         'Chrome/60.0.3112.113 Whale/1.0.41.8 Safari/537.36'
    with requests.session() as sess:
        sess.headers.update({'user-agent': ua})

        entry_id = 1
        plink = f'{base}/{entry_id}'
        with sess.get(plink) as resp:
            soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml',
                                                parse_only=article_strainer)
            article_mkdn: str = html2text(soup.prettify())
            article_mkdn_main = article_mkdn.split('공감')[0]
            print(article_mkdn_main)


def help() -> typing.NoReturn:
    msg = f'usage: python3 {__file__} <tistory blog host>'
    sys.exit(msg)


if __name__ == '__main__':
    main(sys.argv)
