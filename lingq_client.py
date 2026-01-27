import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
)


class Hint(TypedDict, total=False):
    id: int
    locale: str
    text: str
    popularity: int


class Card(TypedDict, total=False):
    pk: int
    term: str
    fragment: str
    status: int
    extended_status: Optional[int]
    srs_due_date: str
    hints: List[Hint]
    tags: List[str]


class HintCreate(TypedDict):
    locale: str
    text: str


class LingQApiError(RuntimeError):
    pass


class LingQClient:
    BASE_URL = "https://www.lingq.com/api"

    def __init__(
        self, api_token: str, *, base_url: str = BASE_URL, timeout_s: int = 30
    ):
        self._token = api_token  # never log this
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._logger = logging.getLogger(__name__)

    def list_cards(
        self,
        language: str,
        page_size: int = 200,
        status_filter: Optional[Union[int, Sequence[int]]] = None,
        srs_due: Optional[Union[bool, int]] = None,
    ) -> Iterator[Card]:
        params: List[Tuple[str, str]] = [("page", "1"), ("page_size", str(page_size))]
        if status_filter is not None:
            if isinstance(status_filter, int):
                params.append(("status", str(status_filter)))
            else:
                for s in status_filter:
                    params.append(("status", str(int(s))))
        if srs_due is not None:
            params.append(("srs_due", "1" if bool(srs_due) else "0"))

        url = self._make_url(f"/v3/{language}/cards/", params)
        while url:
            payload = self._request_json("GET", url)
            results = payload.get("results") or []
            for item in results:
                if isinstance(item, dict):
                    yield item  # type: ignore[misc]
            next_url = payload.get("next")
            url = next_url if isinstance(next_url, str) and next_url else ""

    def search_cards(self, language: str, search_term: str) -> List[Card]:
        params: List[Tuple[str, str]] = [
            ("page", "1"),
            ("page_size", "200"),
            ("search", search_term),
        ]
        url = self._make_url(f"/v3/{language}/cards/", params)
        out: List[Card] = []
        while url:
            payload = self._request_json("GET", url)
            results = payload.get("results") or []
            for item in results:
                if isinstance(item, dict):
                    out.append(item)  # type: ignore[arg-type]
            next_url = payload.get("next")
            url = next_url if isinstance(next_url, str) and next_url else ""
        return out

    def create_card(
        self,
        language: str,
        term: str,
        hints: Sequence[HintCreate],
        *,
        fragment: Optional[str] = None,
    ) -> Card:
        body: Dict[str, Any] = {"term": term, "hints": list(hints)}
        frag = (fragment or "").strip()
        if frag:
            # LingQ supports setting fragment on create (POST). Patch support
            # is not reliable, so we only send it on create.
            body["fragment"] = frag
        url = self._make_url(f"/v3/{language}/cards/", None)
        payload = self._request_json("POST", url, body)
        if not isinstance(payload, dict):
            raise LingQApiError("Unexpected create_card response")
        return payload  # type: ignore[return-value]

    def patch_card(self, language: str, pk: int, data: Dict[str, Any]) -> Card:
        url = self._make_url(f"/v3/{language}/cards/{pk}/", None)
        payload = self._request_json("PATCH", url, data)
        if not isinstance(payload, dict):
            raise LingQApiError("Unexpected patch_card response")
        return payload  # type: ignore[return-value]

    def review_card(self, language: str, pk: int) -> Dict[str, Any]:
        url = self._make_url(f"/v2/{language}/cards/{pk}/review/", None)
        payload = self._request_json("POST", url, {})
        if not isinstance(payload, dict):
            raise LingQApiError("Unexpected review_card response")
        return payload

    def _make_url(self, path: str, params: Optional[Sequence[Tuple[str, str]]]) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = self._base_url + path
        if not params:
            return url
        return url + "?" + urllib.parse.urlencode(list(params), doseq=True)

    def _request_json(
        self, method: str, url: str, json_body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        raw = self._request(method, url, json_body=json_body)
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        raise LingQApiError("Unexpected JSON response type")

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        max_5xx_retries: int = 3,
        max_429_retries: int = 5,
    ) -> Any:
        body_bytes: Optional[bytes]
        if json_body is None:
            body_bytes = None
        else:
            body_bytes = json.dumps(json_body).encode("utf-8")

        headers = {
            "Authorization": f"Token {self._token}",
            "Accept": "application/json",
            "User-Agent": "lingq-anki",
        }
        if body_bytes is not None:
            headers["Content-Type"] = "application/json"

        attempt_5xx = 0
        attempt_429 = 0

        while True:
            self._logger.debug("LingQ request %s %s", method, self._loggable_url(url))
            req = urllib.request.Request(
                url=url, data=body_bytes, headers=headers, method=method
            )

            try:
                with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                    status = getattr(resp, "status", None) or resp.getcode()
                    request_id = self._extract_request_id(resp.headers)
                    self._logger.debug(
                        "LingQ response %s request-id=%s", status, request_id or "-"
                    )

                    raw = resp.read()
                    if not raw:
                        return None
                    try:
                        return json.loads(raw.decode("utf-8"))
                    except json.JSONDecodeError as e:
                        raise LingQApiError("Non-JSON response from LingQ") from e

            except urllib.error.HTTPError as e:
                status = e.code
                request_id = self._extract_request_id(getattr(e, "headers", None))
                self._logger.debug(
                    "LingQ response %s request-id=%s", status, request_id or "-"
                )

                if status == 429 and attempt_429 < max_429_retries:
                    attempt_429 += 1
                    sleep_s = self._retry_after_seconds(e.headers)
                    time.sleep(sleep_s)
                    continue

                if 500 <= status < 600 and attempt_5xx < max_5xx_retries:
                    sleep_s = 2**attempt_5xx
                    attempt_5xx += 1
                    time.sleep(sleep_s)
                    continue

                raise self._http_error_to_exception(e) from e

            except (urllib.error.URLError, TimeoutError) as e:
                if attempt_5xx < max_5xx_retries:
                    sleep_s = 2**attempt_5xx
                    attempt_5xx += 1
                    time.sleep(sleep_s)
                    continue
                raise LingQApiError("Network error talking to LingQ") from e

    def _retry_after_seconds(self, headers: Any) -> int:
        retry_after = None
        if headers is not None:
            try:
                retry_after = headers.get("Retry-After")
            except Exception:
                retry_after = None

        seconds = 5
        if retry_after:
            try:
                seconds = int(str(retry_after).strip())
            except ValueError:
                seconds = 5

        return seconds + 3  # small buffer

    def _extract_request_id(self, headers: Any) -> Optional[str]:
        if headers is None:
            return None

        for key in ("X-Request-Id", "X-Request-ID", "X-Requestid"):
            try:
                val = headers.get(key)
            except Exception:
                val = None
            if val:
                return str(val)
        return None

    def _http_error_to_exception(self, e: urllib.error.HTTPError) -> LingQApiError:
        body_preview = ""
        try:
            raw = e.read()
            if raw:
                text = raw.decode("utf-8", errors="replace")
                body_preview = text[:500]
        except Exception:
            body_preview = ""

        msg = f"LingQ API HTTP {e.code}"
        if body_preview:
            msg += f": {body_preview}"
        return LingQApiError(msg)

    def _loggable_url(self, url: str) -> str:
        # Ensure we never log tokens if they ever appear in query params.
        try:
            parsed = urllib.parse.urlsplit(url)
            if not parsed.query:
                return url
            q = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            redacted = []
            for k, v in q:
                if k.lower() in {"token", "api_token", "authorization"}:
                    redacted.append((k, "REDACTED"))
                else:
                    redacted.append((k, v))
            new_query = urllib.parse.urlencode(redacted, doseq=True)
            return urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
            )
        except Exception:
            return url
