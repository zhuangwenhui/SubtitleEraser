# tools/ — 外部二进制(不入 git,按下述方式获取)

## ffmpeg/(静态版 7.0.2,含 libass/libfreetype/fontconfig)

```bash
cd tools
curl -sL -o ffmpeg-static.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar xf ffmpeg-static.tar.xz && rm ffmpeg-static.tar.xz
mv ffmpeg-*-amd64-static ffmpeg
```

代码通过 `subtitle_eraser/ffmpeg_tools.py` 解析:环境变量 FFMPEG_BIN/FFPROBE_BIN > PATH > 本目录。

## fonts/(中文字幕渲染字体,OFL 许可)

```bash
cd tools/fonts
curl -sL -O https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf
```
