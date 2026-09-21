# openTransmit

A small Python/Tkinter radio automation and playout program.

It is designed for a simple station workflow:

- manually queue audio
- double-click library items to add them
- play and remove queue items
- generate an automatic rolling radio playlist
- keep station audio separated into four folders

## Audio layout

```
audio/
├── ads/
├── promos/
├── music/
└── idents/
```

Supported audio formats:

- MP3
- WAV
- OGG
- FLAC
- M4A
- AAC
- Opus

Put your station audio in the appropriate folder.

## Requirements

Python 3.10+ with Tkinter, plus either:

- mpv (recommended), or
- ffplay from FFmpeg

On Arch/CachyOS:

```bash
sudo pacman -S python tk mpv
```

## Run

```bash
python radio.py
```

The **Auto Radio** mode continuously keeps the queue supplied. The current first version uses a simple randomized format:

- music: about 70%
- ads: about 15%
- promos: about 8%
- idents: about 7%

If a category is empty, its slots fall back to music.

## Project direction

openTransmit is intended to stay simple and local. A future version can add:

- scheduled clocks
- fixed ad breaks
- jingles between songs
- metadata/RDS output
- live input
- SimTx/GNU Radio integration
- crossfade
- station presets
