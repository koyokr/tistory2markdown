#!/usr/bin/python3
# -*- coding: utf-8 -*-

import imghdr
import os
import re
import sys
import shutil
from datetime import datetime
from time import sleep
from typing import Generator, List, NoReturn, Tuple
from xml.etree import ElementTree

import html2text
from bs4 import BeautifulSoup
from requests import Session


Post = Tuple[int, str, Tuple[str], datetime, str]


def decompose_not_content(article: BeautifulSoup) -> None:
    clss = ('titleWrap', 'container_postbtn', 'relatedWrap', 'author')
    for cls in clss: 
        div = article.find('div', {'class': cls})
        if div:
            div.decompose()


def get_post(html: str) -> Post:
    soup = BeautifulSoup(html, 'html5lib')
    article = soup.find('article')

    if not article:
        raise ValueError('Not found article element')
    info = article.find('div', {'class': 'titleWrap'})
    if not info:
        raise ValueError('Not found div elements with class titleWrap')

    a = info.find('a')
    entry = int(a.get('href').split('/')[-1])
    title = a.get_text()
    categories_text = info.find('span', {'class': 'category'}).get_text() \
                          .replace('분류없음', 'uncategorized')
    categories = tuple(categories_text.strip().split('/'))
    date_text = info.find('span', {'class': 'date'}).get_text()
    date = datetime.strptime(date_text.strip(), '%Y.%m.%d %H:%M')

    def indent_to_backquote(text):
        def remove_indent(t):
            for line in t.splitlines():
                if line[0:4] == '    ':
                    yield line[4:]
                elif line[0:1] == '\t':
                    yield line[1:]
                else:
                    yield line
        p = re.compile(r'    .+\n(?:    .*?\n)+')
        text_backquote = p.sub('\n```\n\\g<0>```\n', text)
        return '\n'.join(remove_indent(text_backquote))

    decompose_not_content(article)
    h = html2text.HTML2Text(bodywidth=0)
    content = indent_to_backquote(h.handle(article.prettify()))
    return entry, title, categories, date, content


def get_entry_last(sess: Session, base: str) -> int:
    rlink = f'{base}/rss'
    with sess.get(rlink) as resp:
        rss = ElementTree.fromstring(resp.text)
        plink_last = rss.find('channel').find('item').find('link').text
        entry_last = int(plink_last.split('/')[-1])
    return entry_last


def iter_post(sess: Session, base: str) -> Generator[Post, None, None]:
    entry_last = get_entry_last(sess, base)
    for entry in range(1, entry_last + 1):
        plink = f'{base}/{entry}'
        with sess.get(plink) as resp:
            try:
                yield get_post(resp.text)
            except ValueError as e:
                print(f'[!] {e}', file=sys.stderr)


def main(argv: Tuple[str]) -> None:
    if len(argv) != 2:
        help()

    scheme = 'http'
    host = argv[1]
    base = f'{scheme}://{host}'
    ua = 'Mozilla/5.0 (Windows NT 6.1; rv:60.0) Gecko/20100101 Firefox/60.0'
    mdname = 'index.md'
    re_img = re.compile(r'!\[\]\(' \
                        r'(https://t1\.daumcdn\.net/cfile/tistory/\w+)' \
                        r'\)')

    try:
        os.makedirs(host)
    except FileExistsError as e:
        if input(f'[!] {e.args[1]}: Remove "{host}"? (y/n):').lower() == 'y':
            shutil.rmtree(host)
            os.makedirs(host)
        else:
            return

    with Session() as sess:
        sess.headers.update({'user-agent': ua})
        for entry, title, categories, date, content in iter_post(sess, base):
            category = categories[0]
            categories_path = '/'.join(categories)
            categories_text = ', '.join(categories)

            dirpath = f'{host}/{categories_path}/{entry}'
            mdpath = f'{dirpath}/{mdname}'
            os.makedirs(dirpath)

            index = 0
            def get_img_path_save(m) -> str:
                nonlocal index
                index += 1
                ilink = m.group(1)
                ipath = f'{dirpath}/img_{index}'
                with sess.get(ilink, stream=True) as resp:
                    with open(ipath, 'wb') as f:
                        f.write(resp.content)
                ext = imghdr.what(ipath)
                ipath_ext = f'{ipath}.{ext}'
                shutil.move(ipath, ipath_ext)
                print(ipath_ext)
                iname = f'img_{index}.{ext}'
                return f'![{iname}]({iname})'
            content_with_img = re_img.sub(get_img_path_save, content)
            title = f'"{title}"' if ':' in title else title

            buf = f'---\n' \
                  f'title: {title}\n' \
                  f'categories: [{categories_text}]\n' \
                  f'slug: {entry}\n' \
                  f'date: {date}\n' \
                  f'---\n' \
                  f'{content_with_img}'
            
            with open(mdpath, 'w') as f:
                f.write(buf)
            print(mdpath)
            sleep(0.1)



def help() -> NoReturn:
    msg = f'usage: python3 {__file__} <tistory blog host>'
    sys.exit(msg)


if __name__ == '__main__':
    main(tuple(sys.argv))
