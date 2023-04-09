import aiohttp
import asyncio

from datetime import datetime
from typing import Optional, Self
from dataclasses import dataclass
from Nerris.nationstates.nation import Nation as Nation

__all__ = ["NationStatesClient"]

@dataclass(frozen=True)
class Allowable:
    amount: int
    seconds: int

@dataclass
class Requests:
    allowable: Allowable
    limit: int
    remaining: int
    resets: int

    last_request: datetime
    request_count: int

    retry_after: Optional[int]

class NationStatesClient:
    api_version = 11
    base_url = "https://nationstates.net/cgi-bin/api.cgi?"
    version_shard = "a=version"
    nation_shard = "nation={}"
    verify_shard = 'a=verify&nation={}&checksum={}'

    requests: Requests
    _allow_api_mismatch = False

    def __init__(self, session: aiohttp.ClientSession, user_agent="NerrisBot-Suns_Reach"):
        self.user_agent = user_agent
        self.session = session
        self.requests = Requests(Allowable(0,0), 0, 0, 0, 0, 0, 0)
        self.headers = {'User-Agent': self.user_agent}

    def get_verify_url(self, token: Optional[str] = None):
        if token is None:
            return "https://nationstates.net/page=verify_login"
        return "https://nationstates.net/page=verify_login?token={}".format(token)

    async def verify(self, nation: Nation | str, code: str, token: Optional[str] = None) -> tuple[Nation, bool]:
        verify = '{}{}'.format(self.base_url, self.verify_shard)
        try:
            verify = verify.format(nation.name.replace(" ", "_"), code)
        except AttributeError:
            verify = verify.format(nation.replace(" ", "_"), code)

        verify = '{}&q=name+region'.format(verify)

        if token is not None:
            verify = '{}&token={}'.format(verify, token)

        response = await self._make_request(verify, self.headers)
        print(response)
        name = response.split("<NAME>")[1].split("</NAME>")[0]
        region = response.split("<REGION>")[1].split("</REGION>")[0]
        verified = response.split("<VERIFY>")[1].split("</VERIFY>")[0]
        return bool(int(verified)), Nation(name, nation, region)

    async def _make_request(self, url, headers) -> str:
        if self.requests.remaining > 0 and self.requests.retry_after is None:
            async with self.session.get(url, headers=headers) as response:
                self.update_requests(response.headers)
                if response.status != 429:
                    return await response.text()
                else:
                    return await _make_reqeust(self, url, headers)
        else:
            if self.requests.retry_after is not None:
                await asyncio.sleep(retry_after)
                self.requests.retry_after = None
                return await self._make_request(url, headers)
            else:
                sleep_time = datetime.utcnow() - last_request
                await asyncio.sleep(sleep_time)
                self.requests.remaining = self.requests.limit
                self.requests.request_count = 0


    async def build(self) -> Self:
        await self._check_version()
        return self

    def update_requests(self, headers):
        amount, seconds = headers["RateLimit-Policy"].split(";")
        limit = int(headers["RateLimit-Limit"])
        remaining = int(headers["RateLimit-Remaining"])
        reset = int(headers["RateLimit-Reset"])
        try:
            retry_after = int(headers['Retry-After'])
        except KeyError:
            retry_after = None

        seconds = int(seconds.split("=")[1])
        amount = int(amount)

        self.requests = Requests(Allowable(amount, seconds), limit, remaining, reset, datetime.utcnow(), self.requests.request_count + 1, retry_after)


    async def _check_version(self):
        async with self.session.get('{}{}'.format(self.base_url, self.version_shard), headers=self.headers) as response:
            headers = response.headers
            version = int(await response.text())

            if version != self.api_version and not self._allow_api_mismatch:
                raise BaseException("NationStates API Version: {} is not equal to expected version {}! Please Update the NS Client!".format(version, self.api_version))
            elif version != self.api_version:
                #TODO: Log here
                pass

            self.update_requests(response.headers)
