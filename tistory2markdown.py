#!/usr/bin/python3
# -*- coding: utf-8 -*-

import imghdr
import os
import re
import sys
import shutil
from datetime import datetime
from typing import Generator, List, NamedTuple, NoReturn, Tuple
from xml.etree import ElementTree

from html2text import HTML2Text
from bs4 import BeautifulSoup
from requests import Session


USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; rv:60.0) Gecko/20100101 Firefox/60.0'


class Post(NamedTuple):
    entry: int
    title: str
    categories: Tuple[str, ...]
    date: datetime
    content: str


def lint_codeblock(text: str) -> str:
    def remove_indent(t):
        for line in t.splitlines():
            if line[0:4] == '    ':
                yield line[4:]
            elif line[0:1] == '\t':
                yield line[1:]
            else:
                yield line
    text = re.sub(r'    .+\n(?:    .*?\n)+', '\n```\n\\g<0>```\n', text)
    text = '\n'.join(remove_indent(text))
    text = text.replace('\n\n```\n\n', '\n```\n\n')
    return text


def lint_table(text: str) -> str:
    t = re.sub(r' \n\n\| \n\n',               '|',     text)
    t = re.sub(r' \n\n\|',                    '|',        t)
    t = re.sub(r'(.*?(?:\|.*?)+\|?)   ?\n  ', '|\\g<1>|', t)
    t = re.sub(r'(\|(?:.*?\|)+\n)+',          '\\g<0>\n', t)
    return text


def decompose_not_content(article: BeautifulSoup):
    clss = ('titleWrap', 'container_postbtn', 'relatedWrap', 'author')
    for cls in clss: 
        div = article.find('div', {'class': cls})
        if div:
            div.decompose()


def get_post(html: str) -> Post:
    article = BeautifulSoup(html, 'html5lib').find('article')
    if not article:
        raise ValueError('Not found article element')

    info = article.find('div', {'class': 'titleWrap'})
    if not info:
        raise ValueError('Not found div elements with class titleWrap')

    a = info.find('a')
    entry = get_entry(a.get('href'))
    title = a.get_text()

    category = info.find('span', {'class': 'category'})
    category_text = category.get_text().replace('분류없음', 'uncategorized')
    categories = tuple(category_text.strip().split('/'))

    date_text = info.find('span', {'class': 'date'}).get_text()
    date = datetime.strptime(date_text.strip(), '%Y.%m.%d %H:%M')

    decompose_not_content(article)
    content = HTML2Text(bodywidth=0).handle(article.prettify())
    content = lint_codeblock(content)
    content = lint_table(content)
    return Post(entry, title, categories, date, content)


def get_entry(url: str) -> int:
    path = url.split('/')[-1]
    return int(path)


class Tistory():
    __slot__ = ('sess', 'host', 'link')

    def __init__(self, host: str):
        self.sess: Session = Session()
        self.host: str = host
        self.link: str = f'http://{host}'
        self.sess.headers.update({'user-agent': USER_AGENT})

    def __del__(self):
        self.sess.close()

    def save_post_all(self):
        for post in self.iter_post():
            self.save_post(post)

    def iter_post(self) -> Generator[Post, None, None]:
        for entry in range(1, self.get_entry_last() + 1):
            with self.sess.get(f'{self.link}/{entry}') as resp:
                try:
                    yield get_post(resp.text)
                except ValueError as e:
                    print(f'[!] {e}', file=sys.stderr)

    def get_entry_last(self) -> int:
        with self.sess.get(f'{self.link}/rss') as resp:
            rss = ElementTree.fromstring(resp.text)
        url_post_last = rss.find('channel').find('item').find('link').text
        entry_last = get_entry(url_post_last)
        return entry_last

    def fix_content_save_img(self, dirpath: str, content: str) -> str:
        index = 0
        def get_img_path_download(m) -> str:
            nonlocal index
            index += 1
            imgurl = m.group(1)
            imgpath_temp = f'{dirpath}/img_{index}'
            with self.sess.get(imgurl, stream=True) as resp:
                with open(imgpath_temp, 'wb') as f:
                    f.write(resp.content)
            ext = imghdr.what(imgpath_temp)
            imgpath = f'{imgpath_temp}.{ext}'
            shutil.move(imgpath_temp, imgpath)
            print(imgpath)
            imgname = os.path.basename(imgpath)
            return f'![{imgname}]({imgname})'
        return re.sub(r'!\[\]\((.*?)\)', get_img_path_download, content)

    def save_post(self, post: Post):
        entry, title, categories, date, content = post
        categories_path = '/'.join(categories)
        categories_text = ', '.join(categories)
        dirpath = f'{self.host}/{categories_path}/{entry}'
        os.makedirs(dirpath)

        content = self.fix_content_save_img(dirpath, content)
        title = f'"{title}"' if ':' in title else title

        buf = f'---\n' \
              f'title: {title}\n' \
              f'categories: [{categories_text}]\n' \
              f'slug: {entry}\n' \
              f'date: {date}\n' \
              f'url: {entry}\n' \
              f'---\n' \
              f'{content}'
        
        mdpath = f'{dirpath}/index.md'
        with open(mdpath, 'w') as f:
            f.write(buf)
        print(mdpath)


def main(argv: Tuple[str]):
    if len(argv) != 2:
        help()
    host = argv[1]

    if os.path.exists(host):
        if input(f'[!] File exists: Remove "{host}"? (y/N):').lower() == 'y':
            shutil.rmtree(host)
        else:
            return
    os.makedirs(host)

    tistory = Tistory(host)
    tistory.save_post_all()


def help() -> NoReturn:
    msg = f'usage: python3 {__file__} <tistory blog host>'
    sys.exit(msg)


if __name__ == '__main__':
    main(tuple(sys.argv))
