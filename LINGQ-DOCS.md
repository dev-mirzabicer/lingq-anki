The following is the relevant parts from LingQ API v2 Docs. There's nothing else that's relevant. Feel _more than free_ to test things out using cURL to discover more things about it (such as exact structures of the results).
<docs>
LingQs

---

LingQs resource provides information about all LingQs.

# List Resource

## GET

Returns a list of all user LingQs for particular language

================== ================================================================
Property Description
================== ================================================================
page_size Page size
page Current page number
search Term to search
search_criteria Exact match by default:
_ contains
_ startsWith
_ endsWith
_ phraseContaining
sort Sort by:
_ alpha
_ date
_ status
_ importance
content_id Lesson PK
tags A list of tags
================== ================================================================

.. code-block:: bash

GET /api/v2/{language_code}/cards/?page_size=25&page=1 HTTP/1.1

.. code-block:: js

    {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
            {
                "pk": 96177027,
                "url": "https://www.lingq.com/api/v2/en/cards/96177027/",
                "term": "abetting",
                "fragment": "...spectacle of Reagan's party's abetting the hijacking of American...",
                "importance": 0,
                "status": 0,
                "extended_status": null,
                "last_reviewed_correct": null,
                "srs_due_date": "2019-03-07T08:38:08.169320",
                "notes": "",
                "audio": null,
                "altScript": [],
                "transliteration": [],
                "words": [
                    "abetting"
                ],
                "tags": [],
                "hints": [
                    {
                        "id": 3213711,
                        "locale": "ru",
                        "text": "ÑÐ¾ÑƒÑ‡Ð°ÑÑ‚Ð¸Ðµ",
                        "term": "abetting",
                        "popularity": 26,
                        "is_google_translate": false,
                        "flagged": false
                        },
                    {
                        "id": 36833966,
                        "locale": "fr",
                        "text": "encourageant",
                        "term": "abetting",
                        "popularity": 1,
                        "is_google_translate": false,
                        "flagged": false
                    }
                ]
            }
        ]
    }

# Export LingQs

## GET

================== ================================================================
Property Description
================== ================================================================
cards LingQ PK
export_type Format:
_ csv
_ anki
================== ================================================================

.. code-block:: bash

GET /api/v2/{language_code}/cards/export/?cards=96177027&cards=85904717 HTTP/1.1

Hints

---

Returns a list of meanings for particular word in specific language

## GET

================== ================================================================
Property Description
================== ================================================================
term Term to search
locale Dictionary language
all Whether return all hints or only top ones
================== ================================================================

.. code-block:: bash

GET /api/v2/es/hints/search/?term=libro&locale=en HTTP/1.1

.. code-block:: js

    [
      {
        "id": 171872,
        "locale": "en",
        "text": "book",
        "term": "libro",
        "popularity": 2981,
        "is_google_translate": false,
        "flagged": false
      },
      {
        "id": 15924154,
        "locale": "en",
        "text": "book (masculine singular noun)",
        "term": "libro",
        "popularity": 58,
        "is_google_translate": false,
        "flagged": false
      },
      {
        "id": 21715380,
        "locale": "en",
        "text": "[n. m.]  book, ledger",
        "term": "libro",
        "popularity": 17,
        "is_google_translate": false,
        "flagged": false
      }
    ]

</docs>
