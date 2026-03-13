---
layout: default
title: "カテゴリ一覧"
description: "日刊AIエージェントのカテゴリ別記事一覧"
permalink: /categories/
---

<div class="page-header">
  <h1>カテゴリ一覧</h1>
  <p>トピックのカテゴリ別に記事を探せます</p>
</div>

{% assign categories = "" | split: "" %}
{% for post in site.posts %}
  {% for tag in post.tags %}
    {% unless categories contains tag %}
      {% assign categories = categories | push: tag %}
    {% endunless %}
  {% endfor %}
{% endfor %}
{% assign categories = categories | sort %}

{% for cat in categories %}
<section class="category-section">
  <h2>
    {% assign tag_key = cat | downcase | replace: ' ', '-' %}
    <span class="tag tag-{{ tag_key }}">{{ cat }}</span>
  </h2>
  <ul class="archive-list">
    {% for post in site.posts %}
      {% if post.tags contains cat %}
      <li>
        <span class="arc-date">{{ post.date | date: "%Y-%m-%d" }}</span>
        <span class="arc-title"><a href="{{ site.baseurl }}{{ post.url }}">{{ post.title }}</a></span>
      </li>
      {% endif %}
    {% endfor %}
  </ul>
</section>
{% endfor %}

{% if categories.size == 0 %}
<p style="color:#718096;">まだ記事がありません。</p>
{% endif %}
