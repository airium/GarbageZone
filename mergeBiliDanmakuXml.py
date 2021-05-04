# coding=utf-8

from __future__ import annotations

try:
    import sys
    assert sys.version_info >= (3, 8)

    import re
    import json
    import argparse
    from pathlib import Path
    from functools import partial
    from operator import methodcaller, attrgetter, itemgetter
    from datetime import datetime, timedelta as td
    from binascii import crc32

    from tqdm import tqdm                                                       # pip install tqdm
    from dateutil.parser import isoparse                                        # pip install python-dateutil
    from dateutil.tz import tzlocal
    from bs4 import BeautifulSoup as BS, Tag as TAG, NavigableString as NS      # pip install beautifulsoup4
except AssertionError:
    input('Please use Python 3.8 or above')
    exit()
except ImportError:
    input('Please check Python version (3.8+) and dependency (tqdm, dateutil and beautifulsoup4)')
    exit()

'''=====================================================================================================================
CONFIGURABLE PARAMETERS
====================================================================================================================='''

TIME_TOLERANCE = 120
# a pair of messages from two recordings will be merged if sent by the same user and within this interval
# use 120 since https://matsuri.icu records danmaku ~100 sec ahead of actual live start, otherwise 10 is OK

TIME_ZONE = tzlocal()
# the time zone

ID_TABLE_PATH = Path(__file__).stem  + '_crc2uid.json'
READ_ID_TABLE = True
UPDATE_ID_TABLE = True
WRITE_ID_TABLE = True
# danmaku downloaded from https://matsuri.icu removes text style and replaces user id with its crc32
# if you locally use Bili-Rec (which saves style and id), this script can store the mapping from crc32 to the true id
# here you can set the filename to save the mapping (alongside the script by default), and whether to use it

BILIREC_FILENAME_PATTERN = r'录制-(?P<room_id>[0-9]+)-(?P<date>20[0-9]{6})-(?P<time>[0-9]{6})-.*'
MATSURI_FILENAME_PATTERN = r'.*_(?P<millisec>1[0-9]{12})'


'''=====================================================================================================================
AUTO-DETERMINED PARAMETERS
====================================================================================================================='''

ID_TABLE = json.loads(table.read_bytes()) if (table := Path(__file__).parent.joinpath(ID_TABLE_PATH)).is_file() else {}
XML_TEMPLATE = '''<?xml-stylesheet type="text/xsl" href="#s"?><i><chatserver>chat.bilibili.com</chatserver><chatid>0</chatid><mission>0</mission><maxlimit>1000</maxlimit><state>0</state><real_name>0</real_name><source>0</source><BililiveRecorder version="Not Applicable" /><BililiveRecorderXmlStyle><z:stylesheet version="1.0" id="s" xml:id="s" xmlns:z="http://www.w3.org/1999/XSL/Transform"><z:output method="html"/><z:template match="/"><html><meta name="viewport" content="width=device-width"/><title>B站录播姬弹幕文件 - <z:value-of select="/i/BililiveRecorderRecordInfo/@name"/></title><style>body{margin:0}h1,h2,p,table{margin-left:5px}table{border-spacing:0}td,th{border:1px solid grey;padding:1px}th{position:sticky;top:0;background:#4098de}tr:hover{background:#d9f4ff}div{overflow:auto;max-height:80vh;max-width:100vw;width:fit-content}</style><h1>B站录播姬弹幕XML文件</h1><p>本文件的弹幕信息兼容B站主站视频弹幕XML格式，可以使用现有的转换工具把文件中的弹幕转为ass字幕文件</p><table><tr><td>录播姬版本</td><td><z:value-of select="/i/BililiveRecorder/@version"/></td></tr><tr><td>房间号</td><td><z:value-of select="/i/BililiveRecorderRecordInfo/@roomid"/></td></tr><tr><td>主播名</td><td><z:value-of select="/i/BililiveRecorderRecordInfo/@name"/></td></tr><tr><td>录制开始时间</td><td><z:value-of select="/i/BililiveRecorderRecordInfo/@start_time"/></td></tr><tr><td><a href="#d">弹幕</a></td><td>共 <z:value-of select="count(/i/d)"/> 条记录</td></tr><tr><td><a href="#guard">上船</a></td><td>共 <z:value-of select="count(/i/guard)"/> 条记录</td></tr><tr><td><a href="#sc">SC</a></td><td>共 <z:value-of select="count(/i/sc)"/> 条记录</td></tr><tr><td><a href="#gift">礼物</a></td><td>共 <z:value-of select="count(/i/gift)"/> 条记录</td></tr></table><h2 id="d">弹幕</h2><div><table><tr><th>用户名</th><th>弹幕</th><th>参数</th></tr><z:for-each select="/i/d"><tr><td><z:value-of select="@user"/></td><td><z:value-of select="."/></td><td><z:value-of select="@p"/></td></tr></z:for-each></table></div><h2 id="guard">舰长购买</h2><div><table><tr><th>用户名</th><th>舰长等级</th><th>购买数量</th><th>出现时间</th></tr><z:for-each select="/i/guard"><tr><td><z:value-of select="@user"/></td><td><z:value-of select="@level"/></td><td><z:value-of select="@count"/></td><td><z:value-of select="@ts"/></td></tr></z:for-each></table></div><h2 id="sc">SuperChat 醒目留言</h2><div><table><tr><th>用户名</th><th>内容</th><th>显示时长</th><th>价格</th><th>出现时间</th></tr><z:for-each select="/i/sc"><tr><td><z:value-of select="@user"/></td><td><z:value-of select="."/></td><td><z:value-of select="@time"/></td><td><z:value-of select="@price"/></td><td><z:value-of select="@ts"/></td></tr></z:for-each></table></div><h2 id="gift">礼物</h2><div><table><tr><th>用户名</th><th>礼物名</th><th>礼物数量</th><th>出现时间</th></tr><z:for-each select="/i/gift"><tr><td><z:value-of select="@user"/></td><td><z:value-of select="@giftname"/></td><td><z:value-of select="@giftcount"/></td><td><z:value-of select="@ts"/></td></tr></z:for-each></table></div></html></z:template></z:stylesheet></BililiveRecorderXmlStyle></i>'''

'''=====================================================================================================================
HELPER CLASSES
====================================================================================================================='''


class Danmaku():


    def __init__(self, tag:TAG, parent:DanmakuRecord=None) -> None:
        # common attrs: type, text, ts
        # for danmu: user, uid, pos, colour, millisec
        # for others: attrs
        self.parent = parent
        if tag.name == 'd':
            self.type = tag.name                            # danmaku type: 'd', 'gift', 'sc', 'guard'
            self.text = tag.text                            # danmaku text
            self.user = tag.get('user', '')                 # bilibili username (it may change)
            self.ts = float((p := tag['p'].split(','))[0])  # TimeStamp in second relative to the start
            self.pos = p[1]                                 # display postion: '1'=regular '4'=bottom
            self.colour = p[3]                              # colour
            if len(p[4]) == 13 and self.user:               # likely from local BiliRec
                self.millisec = p[4]                        # absolute time in millisecond since epoch
            elif len(p[4]) == 10 and parent:                           # likely from https://matsuri.icu
                self.millisec = str(int((parent.st + td(seconds=self.ts)).timestamp() * 1000))
            elif len(p[4]) == 10:
                self.millisec = f'{p[4]}{td(seconds=self.ts).microseconds // 1000:3d}'
            else:
                raise ValueError('Cannot determine danmaku absolute timestamp')
            if READ_ID_TABLE and ID_TABLE and (not self.user):
                self.uid, self.user = id if (id := ID_TABLE.get(p[6])) else (p[6], self.user)  # try lookup
            else:                                           # otherwise, we are using local BiliRec or no ID_TABLE
                self.uid =  p[6]                            # no need to lookup
        else:
            self.type = tag.name
            self.text = tag.text
            self.ts = float((attrs := dict(tag.attrs)).pop('ts'))  # copy the dict to unbind BS object
            self.attrs = attrs

    @property
    def tag(self) -> TAG:
        if self.type == 'd':
            ret = TAG(name='d', attrs={'p':f'{self.ts:.3f},{self.pos},25,{self.colour},{self.millisec},0,{self.uid},0'})
            if self.text: ret.string = self.text
            if self.user: ret['user'] = self.user
        else:
            (attrs := self.attrs.copy())['ts'] = str(self.ts)
            ret = TAG(name=self.type, attrs=attrs)
            if self.text: ret.string = self.text
        return ret

    def __eq__(self, obj: Danmaku) -> bool:
        if (self.type == obj.type) and (self.text == obj.text) and (abs(self.ts - obj.ts) < TIME_TOLERANCE):
            if self.type == 'd':
                if (self.uid == obj.uid) or (self.user == obj.user): # same uid/username
                    if self.colour == '16777215': self.colour = obj.colour      # try updating colour from the other
                    if self.pos == '1': self.pos == obj.pos                     # try updating pos from the other
                    return True
                if self.uid == f'{crc32(bytes(obj.uid, "utf-8")):x}':           # self is from https://matsuri.icu
                    if UPDATE_ID_TABLE: ID_TABLE[self.uid] = [obj.uid, obj.user]
                    self.uid = obj.uid                                          # self should be updated
                    self.user = obj.user
                    self.colour = obj.colour
                    self.pos = obj.pos
                    self.millisec = obj.millisec
                    return True
                if f'{crc32(bytes(self.uid, "utf-8")):x}' == obj.uid: # obj is from https://matsuri.icu
                    if UPDATE_ID_TABLE: ID_TABLE[obj.uid] = [self.uid, self.user]
                    return True
            else:
                if self.attrs == obj.attrs:
                    return True
        return False


class DanmakuRecord():

    def __init__(self, path:Path) -> None:
        assert path.is_file() and path.suffix == '.xml'
        soup = BS(path.read_bytes(), 'xml')

        if (rec_info := soup.find('BililiveRecorderRecordInfo')):       # a latest BiliRec recording
            self.rid = str(rec_info.get('roomid', ''))
            self.name = str(rec_info.get('name', ''))
            self.st = isoparse(rec_info.get('start_time'))
        elif (m := re.match(BILIREC_FILENAME_PATTERN, path.stem)):    # a legacy BiliRec recording
            self.rid = m['room_id']
            self.name = ''
            if (d := soup.find('d')):
                self.st = datetime.fromtimestamp(int((d0 := Danmaku(d)).millisec)/1000.0 - float(d0.ts), TIME_ZONE)
            else:
                self.st = isoparse(f"{m['date']}-{m['time']}")
                self.st.replace(tzinfo=TIME_ZONE)
        elif (m := re.match(MATSURI_FILENAME_PATTERN, path.stem)):    # downloaded from https://matsuri.icu
            self.rid = ''
            self.name = ''
            self.st = datetime.fromtimestamp(int(m['millisec'])/1000, TIME_ZONE)
        else:
            raise ValueError(f'Cannot parse the start time from \'{path}\'')

        self.danmaku_lst = [[*map(partial(Danmaku, parent=self), soup.find_all(name='d'))],
                            [*map(partial(Danmaku, parent=self), soup.find_all(name='sc'))],
                            [*map(partial(Danmaku, parent=self), soup.find_all(name='gift'))],
                            [*map(partial(Danmaku, parent=self), soup.find_all(name='guard'))]]

    def __len__(self) -> int:
        return sum(map(len, self.danmaku_lst))

    def __bool__(self) -> bool:
        return True


'''=====================================================================================================================
MAIN
====================================================================================================================='''

def main(args):

    danmaku_records = [*map(DanmakuRecord, args.input)]
    assert len(rids := [*filter(None, [r.rid for r in danmaku_records])]) == 0 or rids.count(rids[0]) == len(rids)
    rid = rids[0] if rids else ''
    assert len(names := [*filter(None, [r.name for r in danmaku_records])]) == 0 or names.count(names[0]) == len(names)
    name = names[0] if names else ''

    st = (sts := [*map(attrgetter('st'), danmaku_records)])[0]
    offsets = [(t - st).total_seconds() for t in sts]
    output = BS(XML_TEMPLATE, features='xml')
    output.i.append(TAG(name='BililiveRecorderRecordInfo', attrs={'room_id':rid, 'name':name, 'start_time':st.isoformat()}))

    out = []
    tdiffs = {'diff': 0.0, 'num': 0, 'sum': 0.0} # used to record the average time diffs between two recordings
    with tqdm(total=sum(map(len, danmaku_records))) as pbar:
        for rdri, rdr in enumerate(danmaku_records):                                            # Ref_Rec_Idx and Ref_Rec
            tdiffs = {'diff': tdiffs['sum'] / max(1, tdiffs['num']), 'num': 0, 'sum': 0.0}
            for di in range(4):
                for rdi, rd in enumerate(rdr.danmaku_lst[di]):                                  # Ref_Danmaku_Idx and Ref_Danmaku
                    rd.ts += offsets[rdri] + tdiffs['diff']
                    pbar.update(1)
                    for odri, odr in enumerate(danmaku_records[rdri+1:], start=rdri+1):         # Other_DanmakuRecord_Idx and Other_DanmakuRecord
                        for odi, od in enumerate(odr.danmaku_lst[di]):                          # Other_Danmaku_Idx and Other_Danmaku
                            od.ts += offsets[odri]
                            if od.ts - rd.ts > TIME_TOLERANCE:
                                od.ts -= offsets[odri]
                                break
                            if rd == od:
                                danmaku_records[odri].danmaku_lst[di].pop(odi)
                                pbar.update(1)
                                if odri - rdri == 1:
                                    tdiffs['num'] += 1
                                    tdiffs['sum'] += od.ts - rd.ts
                                break
                            od.ts -= offsets[odri]
                    out.append(rd) # place here since in comparison rm will be updated

    output.i.extend([*map(attrgetter('tag'), sorted(out, key=lambda x: x.ts))])
    out_path = args.output if args.output else args.input[0].with_suffix('.merged.xml')
    out_path.write_bytes(bytes(str(output), 'utf_8_sig'))
    if WRITE_ID_TABLE: Path(ID_TABLE_PATH).write_bytes(bytes(json.dumps(ID_TABLE), 'utf-8'))

'''=====================================================================================================================
CLI Interface
====================================================================================================================='''

class _CustomHelpFormatter(argparse.HelpFormatter):

    def __init__(self, prog):
        super().__init__(prog, max_help_position=50, width=100)

    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ', '.join(action.option_strings) + ' ' + args_string

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='tu', formatter_class=lambda prog: _CustomHelpFormatter(prog))
    parser.add_argument('input', type=Path, action='extend', nargs='+',
                        help='xml subtitle fils to merge', metavar='path')
    parser.add_argument('-o', '--output', dest='output', type=Path, nargs=1,
                        help='the desired output location', metavar='path')
    # sys.argv.append(r"Z:\录制-1321846-20210216-130051-【B】NieR_Automata.xml")
    # sys.argv.append(r"Z:\夏诺雅_shanoa_【B】NieR_Automata_1613480435698.xml")
    # # sys.argv.append(r"E:\v\1321846-夏诺雅_shanoa\夏诺雅_shanoa_【B】小小梦魇_1613307688203.xml")
    # # sys.argv.append(r"E:\v\1321846-夏诺雅_shanoa\录制-1321846-20210214-130304-【B】小小梦魇.xml")
    # # sys.argv.append(r"E:\v\1321846-夏诺雅_shanoa\录制-1321846-20210214-130308-【B】小小梦魇.xml")
    main(parser.parse_args())
