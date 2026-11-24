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

## Conversation carousel (Instagram, from 2026-11-22)
- tools/carousel.py renders posts/YYYY-MM-DD/carousel_1.jpg ... carousel_5.jpg from the "carousel" block of content.json
  (question people ask -> my answer -> how-to steps -> one thing to remember -> DM keyword + contact card).
- It prints "CAROUSEL: PASS" only when fonts load, nothing overflows, the locked logo is the right size and the contact card is exact.
- Instagram gets the carousel; YouTube Shorts still gets short.mp4 (title_te is the same question, tips are the steps).

## Conversation video (from 2026-11-22)
- When content.json has "answer_te"/"answer_en", short.mp4 is a chat: the viewer's question bubble, the coach's answer bubble ("నా సమాధానం"), then the steps and the DM keyword + contact card, with the Telugu voice-over. The same video goes to YouTube Shorts and Instagram Reels.
- The logo always sits on the official teal-to-blue gradient (same as the app icon); the "theme" key is ignored.

## Picture-rich design (from 2026-11-25)
- tools/icons/fluent3d: 3D Fluent emoji pictures (MIT). tools/icons.py finds the picture for an emoji.
- Carousel: 7-8 slides on a warm cream background (cover with question + pictures, answer, one slide per step with title + check-list + pictures, remember, DM + contact). Schema in the docstring of tools/carousel.py.
- Video: the conversation Short shows a row of 3D pictures ("icons" in content.json) under the question and a picture on each tip (tip "icon").
