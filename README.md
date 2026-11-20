# nutrilink-media

Daily images and videos for NutriLink By NutriiGlow. Files here are public so Metricool can publish them to Instagram and YouTube Shorts.

- posts/YYYY-MM-DD/post.jpg  - Instagram feed image (1080x1350)
- posts/YYYY-MM-DD/short.mp4 - vertical video for YouTube Shorts (1080x1920)
- posts/YYYY-MM-DD/content.json - the text used for that day
- tools/render.py - renders both files from content.json

Public link format:
https://raw.githubusercontent.com/yedukondalu-thammisetty/nutrilink-media/main/posts/YYYY-MM-DD/post.jpg

## Brand rules (locked)
The logo (tools/brand/logo.svg), the names "NutriLink" / "By NutriiGlow", and the contact block are the same on every post. Only the background colour theme and the day's text change. Do not edit tools/brand/ or the BRAND_/CONTACT_ constants in tools/render.py.
