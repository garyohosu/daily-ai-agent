---
layout: default
title: カテゴリ
---
<style>
  h1 { font-size: 1.5rem; font-weight: 800; margin-bottom: 1.5rem; }
  .category-section { margin-bottom: 2rem; }
  .category-section h2 { font-size: 1.05rem; font-weight: 700; border-left: 4px solid #0070f3; padding-left: 0.6rem; margin-bottom: 0.8rem; }
  .post-list { list-style: none; }
  .post-list li { padding: 0.4rem 0; border-bottom: 1px solid #eee; font-size: 0.95rem; }
  .post-meta { font-size: 0.8rem; color: #888; }
  .ad-unit { margin: 2rem 0; }
</style>

# カテゴリ一覧

<div class="ad-unit">
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="ca-pub-6743751614716161"
       data-ad-slot="auto"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
  <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>

{% assign all_categories = site.posts | map: "categories" | join: "," | split: "," | uniq | sort %}
{% for category in all_categories %}
{% assign cat_posts = site.posts | where_exp: "post", "post.categories contains category" %}
{% if cat_posts.size > 0 %}
<div class="category-section">
  <h2>{{ category }} ({{ cat_posts.size }})</h2>
  <ul class="post-list">
    {% for post in cat_posts %}
    <li>
      <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
      <span class="post-meta">{{ post.date | date: "%Y-%m-%d" }}</span>
    </li>
    {% endfor %}
  </ul>
</div>
{% endif %}
{% endfor %}
