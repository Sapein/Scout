import asyncio
import gzip
import urllib.parse
import typing
from collections import OrderedDict
from collections.abc import Callable
from typing import Optional, Literal, Any

import aiohttp
import aiolimiter
import xmltodict

import Scout
from .constants import *


def create_user_agent(contact_info: str, nation: str, region: Optional[str] = None) -> str:
    """
    Takes in the information and creates a user agent.
    """
    if region:
        return "Scout-Bot/{v} Nation-{n} for Region-{r} Contact-{c}".format(v=Scout.__VERSION__,
                                                                            n=nation,
                                                                            r=region,
                                                                            c=contact_info)
    return "Scout-Bot/{v} Nation-{n} Contact-{c}".format(v=Scout.__VERSION__, n=nation,
                                                         c=contact_info)


class NS_API_Client(typing.Protocol):
    async def get_nation(self, nation: str, shards: Optional[list[str]],
                         *, checksum: Optional[str] = None, user_agent: Optional[str] = None) -> OrderedDict[str, Any] | Any:
        pass

    async def get_region(self, region: str, shards: Optional[list[str]], *, user_agent: Optional[str] = None
                         ) -> OrderedDict[str, Any] | Any:
        pass


class NationStates_Client:
    """Represents the NationStates API and operations we can take against it.

    Attributes:
        api_version: The API Version the API Supports. This should not be changed.
    """
    limiter: aiolimiter
    nationstates_api_url = "https://nationstates.net/cgi-bin/api.cgi?"

    def __init__(self, user_agent: str, session: aiohttp.ClientSession):
        self.api_version = 12
        self.limiter = aiolimiter.AsyncLimiter(BASE_REQUESTS_AMOUNT, BASE_TIME_PERIOD)
        self.headers = {'User-Agent': user_agent}
        self._session = session

    async def _make_request(self, url, *, limiter: aiolimiter.AsyncLimiter,
                            return_raw=False, headers: Optional[dict[str, str]] = None) -> str | aiohttp.ClientResponse:
        headers = headers if not None else self.headers
        async with limiter:
            async with self._session.get(url, headers=headers) as api_response:
                if api_response.status == 429:
                    return await self._make_request(url, return_raw=return_raw, limiter=limiter)

                try:
                    limiter.max_rate = int(api_response.headers.get("RateLimit-Policy").split(";")[0])
                    limiter.time_period = int(api_response.headers.get("RateLimit-Policy").split("=")[1])
                except AttributeError:
                    pass
                return api_response if return_raw else await api_response.text()

    async def get_nation(self, nation_name: str, shards: Optional[list[str]], *,
                         checksum: Optional[str] = None, user_agent: Optional[str] = None) -> OrderedDict[str, Any] | Any:
        headers = {"User-Agent": user_agent} if user_agent is not None else None
        if (shards is not None and "verify" not in shards) or checksum is None:
            response = await self._make_request("{}nation={}{}&v={}".format(self.nationstates_api_url,
                                                                            nation_name,
                                                                            "" if shards is None or len(shards) == 0
                                                                            else "&q={}".format("+".join(shards)),
                                                                            self.api_version),
                                                headers=headers,
                                                limiter=self.limiter)
        else:
            try:
                shards.remove("verify")
            except (ValueError, AttributeError):
                pass

            response = await self._make_request(
                "{}a=verify&nation={}&checksum={}{}&v={}".format(self.nationstates_api_url,
                                                                 nation_name,
                                                                 checksum,
                                                                 "" if shards is None or len(shards) == 0
                                                                 else "&q={}".format("+".join(shards)),
                                                                 self.api_version),
                headers=headers,
                limiter=self.limiter)
        return (await asyncio.to_thread(xmltodict.parse,xml_input=response))["NATION"]

    async def get_region(self, region_name: str, shards: Optional[list[str]], *, user_agent: Optional[str] = None) -> OrderedDict[str, Any] | Any:
        headers = {"User-Agent": user_agent} if user_agent is not None else None
        response = await self._make_request("{}region={}{}&v={}".format(self.nationstates_api_url,
                                                                        region_name,
                                                                        "" if shards is None or len(shards) == 0
                                                                        else "&q={}".format("+".join(shards)),
                                                                        self.api_version),
                                            headers=headers,
                                            limiter=self.limiter)
        return (await asyncio.to_thread(xmltodict.parse, xml_input=response))["REGION"]

    async def get_world(self, shards: list[str], *, user_agent: Optional[str]) -> OrderedDict[str, Any] | Any:
        headers = {"User-Agent": user_agent} if user_agent is not None else None
        response = await self._make_request("{}q={}&v={}".format(self.nationstates_api_url,
                                                                 "+".join(shards),
                                                                 self.api_version),
                                            headers=headers,
                                            limiter=self.limiter)
        return await asyncio.to_thread(xmltodict.parse, xml_input=response)["WORLD"]

    async def get_world_assembly(self, council_id: Literal[1, 2], shards: list[str], *, user_agent: Optional[str]) -> OrderedDict[
                                                                                            str, Any] | Any:
        headers = {"User-Agent": user_agent} if user_agent is not None else None
        response = await self._make_request("{}wa={}{}&v={}".format(self.nationstates_api_url,
                                                                    council_id,
                                                                    "&q={}".format("+".join(shards)),
                                                                    self.api_version),
                                            headers=headers,
                                            limiter=self.limiter)
        return await asyncio.to_thread(xmltodict.parse, xml_input=response)["WA"]

    async def get_verify(self, nation_name: str, code: str, *, user_agent: Optional[str] = None) -> bool:
        headers = {"User-Agent": user_agent} if user_agent is not None else None
        response = await self._make_request("{}a=verify&nation={}&checksum={}".format(self.nationstates_api_url,
                                                                                      urllib.parse.quote(nation_name), code),
                                            headers=headers,
                                            limiter=self.limiter)
        try:
            return bool(int(response.strip()))
        except (TypeError, ValueError):
            return False

    async def get_daily_dump(self, dump_type: Literal["regions", "nations"], *, user_agent: Optional[str] = None):
        # TODO: Make this do something better and probably asyncly.
        headers = {"User-Agent": user_agent} if user_agent is not None else self.headers
        url = "https://nationstates.net/pages/{}.xml.gz".format(dump_type)
        async with self.limiter:
            async with self._session.get(url, headers=headers) as api_response:
                with open("{}.xml.gz".format(dump_type), 'wb') as compressed_dump:
                    await asyncio.to_thread(compressed_dump.write, await api_response.read())


class NationStates_DataDump_Client:
    # TODO make this actually async.
    region_dump_file = "regions.xml.gz"
    nation_dump_file = "nations.xml.gz"

    async def get_nation(self, nation_name: str, shards: Optional[list[str]],
                         checksum: Optional[str] = None) -> OrderedDict[str, Any] | Any:
        # TODO: Respect shards
        nation_requested = None

        def find_nation(_, nation):
            nonlocal nation_requested
            if nation["NAME"].casefold() == nation_name.casefold():
                nation_requested = nation
                return False
            return True

        try:
            await asyncio.to_thread(xmltodict.parse,gzip.GzipFile(self.nation_dump_file), item_depth=2, item_callback=find_nation)
        except xmltodict.ParsingInterrupted:
            pass
        return nation_requested

    async def get_all_regions(self) -> OrderedDict[str, Any] | Any:
        return await asyncio.to_thread(xmltodict.parse, gzip.GzipFile(self.region_dump_file))

    async def get_all_nations(self) -> OrderedDict[str, Any] | Any:
        return await asyncio.to_thread(xmltodict.parse, gzip.GzipFile(self.nation_dump_file))

    async def get_region(self, region_name: str, shards: Optional[list[str]]) -> OrderedDict[str, Any] | Any:
        # TODO: Respect shards
        region_requested = None

        def find_region(_, region):
            nonlocal region_requested
            if region["NAME"].casefold() == region_name.casefold():
                region_requested = region
                return False
            return True

        try:
            await asyncio.to_thread(xmltodict.parse,gzip.GzipFile(self.region_dump_file), item_depth=2, item_callback=find_region)
        except xmltodict.ParsingInterrupted:
            pass
        return region_requested

    async def process_nation_data_dump(self, data_processor: Callable[[Any, Any], bool]) -> None:
        try:
            await asyncio.to_thread(xmltodict.parse,gzip.GzipFile(self.nation_dump_file), item_depth=2, item_callback=data_processor)
        except xmltodict.ParsingInterrupted:
            pass

    async def process_region_data_dump(self, data_processor: Callable[[Any, Any], bool]) -> None:
        try:
            await asyncio.to_thread(xmltodict.parse, gzip.GzipFile(self.region_dump_file), item_depth=2, item_callback=data_processor)
        except xmltodict.ParsingInterrupted:
            pass

