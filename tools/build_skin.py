# -*- coding: utf-8 -*-
"""Generates the Alamo skin XML files.

Run:  python3 tools/build_skin.py
Output: plugin.video.alamo/resources/skins/Default/1080i/*.xml
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'plugin.video.alamo', 'resources', 'skins',
                   'Default', '1080i')

# palette -------------------------------------------------------------------
BG = 'FF07070B'
PANEL = 'CC101018'
TEXT = 'FFF4F4F6'
DIM = 'FF9A9AA6'
GOLD = 'FFE8B44A'
RED = 'FFD8453C'
SHADE = 'CC000000'

WHITE = 'white.png'
FADE_BOTTOM = 'fade_bottom.png'
FADE_LEFT = 'fade_left.png'
FRAME = 'frame.png'
CORNERS = 'corner_mask.png'

ROWS = [101, 102, 103, 104, 105]
TILE_W = 168
TILE_H = 252
CAPTION_H = 52       # room for a title under a grid tile

# Home layout: the focused row never moves. The whole row block slides up by
# exactly one pitch per row so the focused row always sits at ROW_TOP, and the
# hero is drawn *after* the rows so anything scrolling above it is covered.
HERO_H = 520
ROW_TOP = 566        # y of the focused row's posters - fixed, always
ROW_H = 318          # row pitch (poster + title + gap)


def img(left, top, width, height, texture, diffuse=None, aspect='scale',
        extra=''):
    return f'''      <control type="image">
        <left>{left}</left><top>{top}</top>
        <width>{width}</width><height>{height}</height>
        <texture>{texture}</texture>
        <aspectratio>{aspect}</aspectratio>
        {f'<colordiffuse>{diffuse}</colordiffuse>' if diffuse else ''}
        {extra}
      </control>'''


def label(left, top, width, height, text, color=TEXT, font='font13',
          align='left', extra=''):
    return f'''      <control type="label">
        <left>{left}</left><top>{top}</top>
        <width>{width}</width><height>{height}</height>
        <label>{text}</label>
        <font>{font}</font>
        <textcolor>{color}</textcolor>
        <align>{align}</align><aligny>center</aligny>
        {extra}
      </control>'''


def textbox(left, top, width, height, text, color=DIM, font='font12'):
    return f'''      <control type="textbox">
        <left>{left}</left><top>{top}</top>
        <width>{width}</width><height>{height}</height>
        <label>{text}</label>
        <font>{font}</font>
        <textcolor>{color}</textcolor>
        <autoscroll time="3000" delay="6000" repeat="8000">true</autoscroll>
      </control>'''


def button(cid, left, top, width, height, text, icon='', onright='', onleft='',
           ondown='', onup='', visible=''):
    return f'''      <control type="button" id="{cid}">
        <left>{left}</left><top>{top}</top>
        <width>{width}</width><height>{height}</height>
        <texturefocus border="6" colordiffuse="{GOLD}">{WHITE}</texturefocus>
        <texturenofocus border="6" colordiffuse="55FFFFFF">{WHITE}</texturenofocus>
        <label>{text}</label>
        <font>font13</font>
        <textcolor>{TEXT}</textcolor>
        <focusedcolor>FF101014</focusedcolor>
        <align>center</align><aligny>center</aligny>
        {f'<onright>{onright}</onright>' if onright else ''}
        {f'<onleft>{onleft}</onleft>' if onleft else ''}
        {f'<ondown>{ondown}</ondown>' if ondown else ''}
        {f'<onup>{onup}</onup>' if onup else ''}
        {f'<visible>{visible}</visible>' if visible else ''}
      </control>'''


# --------------------------------------------------------------------------
# shared pieces
# --------------------------------------------------------------------------

def background():
    return '\n'.join([
        img(0, 0, 1920, 1080, WHITE, BG),
        img(0, 0, 1920, 1080, '$INFO[Window.Property(Fanart)]', '44FFFFFF',
            'scale', '<fadetime>400</fadetime>'),
    ])


def sidebar(active_hint=''):
    """Thin icon rail on the left - labels only appear when it has focus."""
    items = f'''      <control type="group">
        <left>0</left><top>0</top>
{img(0, 0, 300, 1080, WHITE, 'E60A0A10')}
{img(0, 0, 300, 1080, FADE_LEFT, 'FF000000')}
{img(46, 44, 208, 58, 'logo.png', None, 'keep')}
{label(46, 1006, 220, 30, 'v$INFO[Window.Property(Version)]', DIM, 'font10')}
        <control type="list" id="90">
          <left>24</left><top>170</top>
          <width>252</width><height>560</height>
          <onright>SetFocus(101)</onright>
          <itemlayout width="252" height="72">
            <control type="image">
              <left>14</left><top>18</top><width>36</width><height>36</height>
              <texture>$INFO[ListItem.Icon]</texture>
              <colordiffuse>FF9A9AA6</colordiffuse>
            </control>
            <control type="label">
              <left>70</left><top>0</top><width>170</width><height>72</height>
              <label>$INFO[ListItem.Label]</label>
              <font>font13</font><textcolor>{DIM}</textcolor>
              <aligny>center</aligny>
            </control>
          </itemlayout>
          <focusedlayout width="252" height="72">
            <control type="image">
              <left>0</left><top>6</top><width>252</width><height>60</height>
              <texture border="8">{WHITE}</texture>
              <colordiffuse>22FFFFFF</colordiffuse>
            </control>
            <control type="image">
              <left>0</left><top>10</top><width>4</width><height>52</height>
              <texture>{WHITE}</texture><colordiffuse>{GOLD}</colordiffuse>
            </control>
            <control type="image">
              <left>14</left><top>18</top><width>36</width><height>36</height>
              <texture>$INFO[ListItem.Icon]</texture>
              <colordiffuse>{GOLD}</colordiffuse>
            </control>
            <control type="label">
              <left>70</left><top>0</top><width>170</width><height>72</height>
              <label>$INFO[ListItem.Label]</label>
              <font>font13</font><textcolor>{TEXT}</textcolor>
              <aligny>center</aligny>
            </control>
          </focusedlayout>
        </control>
      </control>'''
    return items


def loading_screen():
    """Full-screen branded loader shown while a section fetches its first page.

    Kodi's own busy dialog (and its home screen) must never be visible between
    two Alamo windows, so every window paints this itself.
    """
    return f'''      <control type="group">
        <visible>!String.IsEmpty(Window.Property(Loading))</visible>
        <animation effect="fade" start="0" end="100" time="150">Visible</animation>
        <animation effect="fade" start="100" end="0" time="250">Hidden</animation>
{img(0, 0, 1920, 1080, WHITE, 'F207070B')}
{img(760, 430, 400, 112, 'logo.png', None, 'keep')}
{img(936, 590, 48, 48, 'spinner.png', GOLD, 'keep', '<animation effect="rotate" end="360" center="auto" time="900" loop="true" condition="true">Conditional</animation>')}
{label(660, 668, 600, 36, '$INFO[Window.Property(LoadingText)]', DIM, 'font13', 'center')}
      </control>'''


def spinner():
    return f'''      <control type="group">
        <visible>!String.IsEmpty(Window.Property(Loading))</visible>
{img(1740, 40, 40, 40, 'spinner.png', GOLD, 'keep', '<animation effect="rotate" end="360" center="auto" time="900" loop="true" condition="true">Conditional</animation>')}
      </control>'''


def poster_layouts(width=TILE_W, height=TILE_H, show_title=False,
                   container_id=None):
    """Netflix style tile.

    ``show_title``    caption under every tile (browse grids).
    ``container_id``  when given, the focus ring and title overlay only render
                      while that container actually has focus - otherwise Kodi
                      keeps drawing the focused layout for the selected item of
                      every row at once.
    """
    cap = CAPTION_H if show_title else 0
    focus_only = (f'<visible>Control.HasFocus({container_id})</visible>'
                  if container_id else '')
    # when the row is not the active one, its selected tile should look like any
    # other tile: dimmed, no gold ring, no title overlay
    unfocused_dim = (f'<visible>!Control.HasFocus({container_id})</visible>'
                     if container_id else '<visible>false</visible>')

    corners = f'''<control type="image">
                <left>0</left><top>0</top><width>{width}</width><height>{height}</height>
                <texture border="14">{CORNERS}</texture>
              </control>'''

    caption_item = ''
    caption_focus = ''
    if show_title:
        caption_item = f'''
            <control type="label">
              <left>0</left><top>{height + 4}</top>
              <width>{width}</width><height>{cap - 6}</height>
              <label>$INFO[ListItem.Label]</label>
              <font>font10</font><textcolor>{DIM}</textcolor>
              <align>center</align><aligny>top</aligny>
              <wrapmultiline>true</wrapmultiline>
            </control>'''
        caption_focus = f'''
              <control type="label">
                <left>-11</left><top>{height + 4}</top>
                <width>{width + 22}</width><height>{cap - 6}</height>
                <label>$INFO[ListItem.Label]</label>
                <font>font12</font><textcolor>{TEXT}</textcolor>
                <align>center</align><aligny>top</aligny>
                <wrapmultiline>true</wrapmultiline>
              </control>'''

    return f'''          <itemlayout width="{width + 22}" height="{height + 26 + cap}">
            <control type="image">
              <left>0</left><top>0</top><width>{width}</width><height>{height}</height>
              <texture background="true">$INFO[ListItem.Art(poster)]</texture>
              <aspectratio aligny="top">scale</aspectratio>
              <fadetime>200</fadetime>
            </control>
            <control type="image">
              <left>0</left><top>0</top><width>{width}</width><height>{height}</height>
              <texture>{WHITE}</texture>
              <colordiffuse>66000000</colordiffuse>
            </control>
            {corners}{caption_item}
          </itemlayout>
          <focusedlayout width="{width + 22}" height="{height + 26 + cap}">
            <control type="group">
              <animation effect="zoom" start="100" end="110" center="{int(width / 2)},{int(height / 2)}" time="180" tween="sine" reversible="true">Focus</animation>
              <control type="image">
                <left>0</left><top>0</top><width>{width}</width><height>{height}</height>
                <texture background="true">$INFO[ListItem.Art(poster)]</texture>
                <aspectratio aligny="top">scale</aspectratio>
                <fadetime>200</fadetime>
              </control>
              <control type="image">
                <left>0</left><top>0</top><width>{width}</width><height>{height}</height>
                <texture>{WHITE}</texture>
                <colordiffuse>66000000</colordiffuse>
                {unfocused_dim}
              </control>
              {corners}
              <control type="group">
                {focus_only}
                <control type="image">
                  <left>-6</left><top>-6</top><width>{width + 12}</width><height>{height + 12}</height>
                  <texture border="10">{FRAME}</texture>
                  <colordiffuse>{GOLD}</colordiffuse>
                </control>
                <control type="image">
                  <left>0</left><top>{height - 78}</top><width>{width}</width><height>78</height>
                  <texture>{FADE_BOTTOM}</texture>
                </control>
                <control type="label">
                  <left>8</left><top>{height - 74}</top><width>{width - 16}</width><height>52</height>
                  <label>$INFO[ListItem.Label]</label>
                  <font>font10</font><textcolor>{TEXT}</textcolor>
                  <aligny>bottom</aligny><wrapmultiline>true</wrapmultiline>
                </control>
                <control type="label">
                  <left>8</left><top>{height - 26}</top><width>{width - 16}</width><height>22</height>
                  <label>$INFO[ListItem.Property(rating)]</label>
                  <font>font10</font><textcolor>{GOLD}</textcolor>
                </control>
              </control>
              <control type="image">
                <left>{width - 56}</left><top>8</top><width>48</width><height>22</height>
                <texture border="4">{WHITE}</texture>
                <colordiffuse>{RED}</colordiffuse>
                <visible>String.IsEqual(ListItem.Property(live),true)</visible>
              </control>
              <control type="label">
                <left>{width - 56}</left><top>8</top><width>48</width><height>22</height>
                <label>LIVE</label><font>font10</font><align>center</align>
                <textcolor>{TEXT}</textcolor>
                <visible>String.IsEqual(ListItem.Property(live),true)</visible>
              </control>{caption_focus}
            </control>
          </focusedlayout>'''


def hero_block(container_id):
    """Big backdrop + title + plot driven by whatever row has focus."""
    return f'''      <control type="group">
        <visible>Control.HasFocus({container_id})</visible>
        <animation effect="fade" start="0" end="100" time="300">Visible</animation>
{img(0, 0, 1920, HERO_H, f'$INFO[Container({container_id}).ListItem.Art(fanart)]', 'FFFFFFFF', 'scale', '<fadetime>400</fadetime>')}
{img(0, HERO_H - 300, 1920, 300, FADE_BOTTOM)}
{img(0, 0, 1100, HERO_H, FADE_LEFT)}
{label(340, 190, 900, 60, f'$INFO[Container({container_id}).ListItem.Label]', TEXT, 'font30_title')}
{label(340, 256, 900, 34, f'$INFO[Container({container_id}).ListItem.Property(year)]  $INFO[Container({container_id}).ListItem.Property(badge)]  $INFO[Container({container_id}).ListItem.Property(rating)]', GOLD, 'font12')}
{textbox(340, 300, 780, 130, f'$INFO[Container({container_id}).ListItem.Property(plot)]')}
      </control>'''


# --------------------------------------------------------------------------
# windows
# --------------------------------------------------------------------------

def home():
    """Netflix-style home.

    The focused row is pinned at ROW_TOP: instead of scrolling the viewport, the
    whole block of rows slides up one pitch per row (one conditional animation
    per row, only one of which can be active). Unfocused rows fade back, and the
    hero is drawn after the rows so rows leaving the top disappear behind it.
    """
    # nav targets: comma lists so navigation skips rows that are empty/hidden
    def targets(index, direction):
        order = (range(index + 1, len(ROWS)) if direction == 'down'
                 else range(index - 1, -1, -1))
        return ','.join(str(ROWS[i]) for i in order)

    rows = []
    for index, cid in enumerate(ROWS):
        top = ROW_TOP + index * ROW_H
        visible = f'!String.IsEmpty(Window.Property(Row{index + 1}Title))'
        down = targets(index, 'down')
        up = targets(index, 'up')
        rows.append(f'''        <control type="group">
          <visible>{visible}</visible>
          <animation effect="fade" start="100" end="38" time="200" condition="!Control.HasFocus({cid})">Conditional</animation>
{label(340, top - 44, 900, 36, f'$INFO[Window.Property(Row{index + 1}Title)]', TEXT, 'font13')}
          <control type="list" id="{cid}">
            <left>340</left><top>{top}</top>
            <width>1560</width><height>{TILE_H + 26}</height>
            <orientation>horizontal</orientation>
            <onleft>90</onleft>
            {f'<onup>{up}</onup>' if up else ''}
            {f'<ondown>{down}</ondown>' if down else ''}
            <scrolltime tween="sine">300</scrolltime>
            <preloaditems>2</preloaditems>
{poster_layouts(container_id=cid)}
          </control>
        </control>''')

    # one slide per row - exactly one condition is true at a time
    slides = '\n'.join(
        f'        <animation effect="slide" start="0,0" end="0,{-index * ROW_H}" '
        f'time="320" tween="sine" condition="Control.HasFocus({cid})">Conditional</animation>'
        for index, cid in enumerate(ROWS) if index)

    body = '\n'.join(rows)
    heroes = '\n'.join(hero_block(cid) for cid in ROWS)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<window>
  <defaultcontrol always="true">101</defaultcontrol>
  <backgroundcolor>{BG}</backgroundcolor>
  <controls>
{img(0, 0, 1920, 1080, WHITE, BG)}

    <!-- rows: drawn first so they slide up behind the hero -->
    <control type="group">
{slides}
{body}
    </control>

    <!-- hero: drawn after the rows, so it covers anything scrolling past it -->
    <control type="group">
{img(0, 0, 1920, HERO_H, WHITE, BG)}
{heroes}
{img(0, HERO_H - 160, 1920, 160, FADE_BOTTOM)}
    </control>

{sidebar()}
{spinner()}
{loading_screen()}
{label(340, HERO_H + 40, 1200, 40, '$INFO[Window.Property(Empty)]', GOLD, 'font13', 'left', '<visible>!String.IsEmpty(Window.Property(Empty))</visible>')}
  </controls>
</window>
'''


def grid():
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<window>
  <defaultcontrol always="true">50</defaultcontrol>
  <backgroundcolor>{BG}</backgroundcolor>
  <controls>
{img(0, 0, 1920, 1080, WHITE, BG)}
{img(0, 0, 1920, 620, '$INFO[Container(50).ListItem.Art(fanart)]', '77FFFFFF', 'scale', '<fadetime>400</fadetime>')}
{img(0, 220, 1920, 400, FADE_BOTTOM)}
{img(0, 0, 1000, 700, FADE_LEFT)}
{label(340, 60, 1000, 60, '$INFO[Window.Property(Heading)]', TEXT, 'font30_title')}
{button(61, 1540, 66, 320, 56, '$INFO[Window.Property(SearchLabel)]', ondown='50', onleft='50', visible='!String.IsEmpty(Window.Property(SearchLabel))')}
{img(1566, 80, 28, 28, 'nav_search.png', GOLD, 'keep', '<visible>!String.IsEmpty(Window.Property(SearchLabel))</visible>')}
{label(340, 124, 1200, 30, '$INFO[Container(50).ListItem.Label]  $INFO[Container(50).ListItem.Property(year)]', GOLD, 'font12')}
{textbox(340, 158, 900, 90, '$INFO[Container(50).ListItem.Property(plot)]')}
    <control type="panel" id="50">
      <left>340</left><top>286</top>
      <width>1570</width><height>794</height>
      <onleft>90</onleft>
      <onup>61</onup>
      <scrolltime tween="sine">300</scrolltime>
      <preloaditems>2</preloaditems>
{poster_layouts(show_title=True, container_id=50)}
    </control>
{sidebar()}
{spinner()}
{loading_screen()}
{label(340, 520, 1200, 40, '$INFO[Window.Property(Empty)]', DIM, 'font13', 'left', '<visible>!String.IsEmpty(Window.Property(Empty))</visible>')}
  </controls>
</window>
'''


def detail():
    ep_item = f'''      <itemlayout width="520" height="118">
        <control type="image">
          <left>0</left><top>4</top><width>186</width><height>108</height>
          <texture background="true">$INFO[ListItem.Art(thumb)]</texture>
          <aspectratio>scale</aspectratio>
        </control>
        <control type="label">
          <left>202</left><top>18</top><width>300</width><height>32</height>
          <label>$INFO[ListItem.Label]</label>
          <font>font12</font><textcolor>{TEXT}</textcolor>
        </control>
        <control type="label">
          <left>202</left><top>54</top><width>300</width><height>28</height>
          <label>$INFO[ListItem.Property(subtitle)]</label>
          <font>font10</font><textcolor>{DIM}</textcolor>
        </control>
      </itemlayout>'''
    ep_focus = f'''      <focusedlayout width="520" height="118">
        <control type="image">
          <left>-4</left><top>0</top><width>194</width><height>116</height>
          <texture border="6">{FRAME}</texture>
          <colordiffuse>{GOLD}</colordiffuse>
        </control>
        <control type="image">
          <left>0</left><top>4</top><width>186</width><height>108</height>
          <texture background="true">$INFO[ListItem.Art(thumb)]</texture>
          <aspectratio>scale</aspectratio>
        </control>
        <control type="label">
          <left>202</left><top>18</top><width>300</width><height>32</height>
          <label>$INFO[ListItem.Label]</label>
          <font>font12</font><textcolor>{GOLD}</textcolor>
        </control>
        <control type="label">
          <left>202</left><top>54</top><width>300</width><height>28</height>
          <label>$INFO[ListItem.Property(subtitle)]</label>
          <font>font10</font><textcolor>{DIM}</textcolor>
        </control>
      </focusedlayout>'''

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<window>
  <defaultcontrol always="true">31</defaultcontrol>
  <backgroundcolor>{BG}</backgroundcolor>
  <controls>
{img(0, 0, 1920, 1080, WHITE, BG)}
{img(0, 0, 1920, 900, '$INFO[Window.Property(Fanart)]', 'FFFFFFFF', 'scale', '<fadetime>500</fadetime>')}
{img(0, 400, 1920, 680, FADE_BOTTOM)}
{img(0, 0, 1200, 1080, FADE_LEFT)}
{img(120, 150, 340, 510, '$INFO[Window.Property(Poster)]', None, 'keep', '<fadetime>300</fadetime>')}
{img(520, 150, 520, 170, '$INFO[Window.Property(Clearlogo)]', None, 'keep', '<visible>!String.IsEmpty(Window.Property(Clearlogo))</visible>')}
{label(520, 190, 1100, 70, '$INFO[Window.Property(Title)]', TEXT, 'font30_title', 'left', '<visible>String.IsEmpty(Window.Property(Clearlogo))</visible>')}
{label(520, 270, 1100, 34, '$INFO[Window.Property(Year)]   $INFO[Window.Property(Runtime)]   $INFO[Window.Property(Genres)]', GOLD, 'font12')}
{label(520, 306, 1100, 32, '$INFO[Window.Property(Tagline)]', DIM, 'font12')}
{textbox(520, 350, 900, 150, '$INFO[Window.Property(Plot)]', TEXT)}
{label(520, 510, 900, 30, 'With $INFO[Window.Property(Cast)]', DIM, 'font10')}
{button(31, 520, 560, 220, 56, 'Play', ondown='40', onright='32')}
{button(32, 756, 560, 190, 56, 'Trailer', onleft='31', onright='33', ondown='40', visible='!String.IsEmpty(Window.Property(HasTrailer))')}
{button(33, 962, 560, 230, 56, 'My List', onleft='32', ondown='40')}
{img(1180, 574, 28, 28, 'check.png', GOLD, 'keep', '<visible>!String.IsEmpty(Window.Property(InMyList))</visible>')}
    <control type="group">
      <visible>!String.IsEmpty(Window.Property(IsTV))</visible>
{label(120, 660, 400, 34, 'Seasons', TEXT, 'font13')}
      <control type="list" id="40">
        <left>120</left><top>700</top>
        <width>340</width><height>340</height>
        <onright>41</onright><onup>31</onup>
        <itemlayout width="340" height="60">
          <control type="label">
            <left>16</left><top>0</top><width>300</width><height>60</height>
            <label>$INFO[ListItem.Label]</label>
            <font>font12</font><textcolor>{DIM}</textcolor><aligny>center</aligny>
          </control>
        </itemlayout>
        <focusedlayout width="340" height="60">
          <control type="image">
            <left>0</left><top>4</top><width>340</width><height>52</height>
            <texture border="8">{WHITE}</texture><colordiffuse>22FFFFFF</colordiffuse>
          </control>
          <control type="label">
            <left>16</left><top>0</top><width>300</width><height>60</height>
            <label>$INFO[ListItem.Label]</label>
            <font>font12</font><textcolor>{GOLD}</textcolor><aligny>center</aligny>
          </control>
        </focusedlayout>
      </control>
      <control type="panel" id="41">
        <left>500</left><top>700</top>
        <width>1380</width><height>360</height>
        <onleft>40</onleft><onup>31</onup>
        <scrolltime tween="sine">250</scrolltime>
{ep_item}
{ep_focus}
      </control>
    </control>
    <control type="group">
      <visible>String.IsEmpty(Window.Property(IsTV))</visible>
{label(120, 690, 400, 34, 'More Like This', TEXT, 'font13')}
      <control type="list" id="42">
        <left>120</left><top>730</top>
        <width>1760</width><height>300</height>
        <orientation>horizontal</orientation>
        <onup>31</onup>
        <scrolltime tween="sine">300</scrolltime>
{poster_layouts(160, 240, container_id=42)}
      </control>
    </control>
{spinner()}
{loading_screen()}
  </controls>
</window>
'''


def sources():
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<window>
  <defaultcontrol always="true">50</defaultcontrol>
  <controls>
{img(0, 0, 1920, 1080, WHITE, 'CC000000')}
{img(460, 200, 1000, 680, WHITE, 'FA0D0D14')}
{img(460, 200, 1000, 4, WHITE, GOLD)}
{label(500, 226, 920, 50, '$INFO[Window.Property(Title)]', TEXT, 'font20')}
{label(500, 280, 920, 34, '$INFO[Window.Property(Status)]', GOLD, 'font12')}
{img(500, 322, 920, 3, WHITE, '22FFFFFF')}
    <control type="group">
      <visible>!String.IsEmpty(Window.Property(Scanning))</visible>
{img(940, 520, 48, 48, 'spinner.png', GOLD, 'keep', '<animation effect="rotate" end="360" center="auto" time="900" loop="true" condition="true">Conditional</animation>')}
    </control>
    <control type="list" id="50">
      <left>500</left><top>350</top>
      <width>920</width><height>500</height>
      <scrolltime tween="sine">200</scrolltime>
      <itemlayout width="920" height="62">
        <control type="label">
          <left>0</left><top>0</top><width>90</width><height>62</height>
          <label>$INFO[ListItem.Property(quality)]</label>
          <font>font12</font><textcolor>{GOLD}</textcolor><aligny>center</aligny>
        </control>
        <control type="label">
          <left>100</left><top>0</top><width>600</width><height>62</height>
          <label>$INFO[ListItem.Label]</label>
          <font>font12</font><textcolor>{TEXT}</textcolor><aligny>center</aligny>
        </control>
        <control type="label">
          <left>710</left><top>0</top><width>210</width><height>62</height>
          <label>$INFO[ListItem.Property(size)]  $INFO[ListItem.Property(provider)]</label>
          <font>font10</font><textcolor>{DIM}</textcolor>
          <align>right</align><aligny>center</aligny>
        </control>
      </itemlayout>
      <focusedlayout width="920" height="62">
        <control type="image">
          <left>-10</left><top>2</top><width>940</width><height>58</height>
          <texture border="8">{WHITE}</texture><colordiffuse>22FFFFFF</colordiffuse>
        </control>
        <control type="image">
          <left>-10</left><top>2</top><width>4</width><height>58</height>
          <texture>{WHITE}</texture><colordiffuse>{GOLD}</colordiffuse>
        </control>
        <control type="label">
          <left>0</left><top>0</top><width>90</width><height>62</height>
          <label>$INFO[ListItem.Property(quality)]</label>
          <font>font12</font><textcolor>{GOLD}</textcolor><aligny>center</aligny>
        </control>
        <control type="label">
          <left>100</left><top>0</top><width>600</width><height>62</height>
          <label>$INFO[ListItem.Label]</label>
          <font>font12</font><textcolor>{TEXT}</textcolor><aligny>center</aligny>
        </control>
        <control type="label">
          <left>710</left><top>0</top><width>210</width><height>62</height>
          <label>$INFO[ListItem.Property(size)]  $INFO[ListItem.Property(provider)]</label>
          <font>font10</font><textcolor>{DIM}</textcolor>
          <align>right</align><aligny>center</aligny>
        </control>
      </focusedlayout>
    </control>
{label(500, 560, 920, 40, 'Nothing found - try another provider', DIM, 'font13', 'center', '<visible>!String.IsEmpty(Window.Property(Empty))</visible>')}
  </controls>
</window>
'''


def main():
    os.makedirs(OUT, exist_ok=True)
    files = {'alamo-home.xml': home(), 'alamo-grid.xml': grid(),
             'alamo-detail.xml': detail(), 'alamo-sources.xml': sources()}
    for name, content in files.items():
        path = os.path.join(OUT, name)
        with open(path, 'w') as handle:
            handle.write(content)
        print('wrote', os.path.normpath(path), len(content), 'bytes')


if __name__ == '__main__':
    main()
