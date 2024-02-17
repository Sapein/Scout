import os

import aiohttp
import pytest

import Scout.core.nationstates.nsapi.ns as ns
from Scout import __VERSION__


# Unit Tests
class Test_Unit_NSAPI:
    def test_create_user_agent(self):
        ua_no_region = ns.create_user_agent(contact_info="Blah", nation="Bigtopia")
        ua_region = ns.create_user_agent(contact_info="Blah", nation="Bigtopia", region="Regionia")
        assert ua_no_region == "Scout-Bot/{v} Nation-{n} Contact-{c}".format(v=__VERSION__, n="Bigtopia", c="Blah")
        assert ua_region == "Scout-Bot/{v} Nation-{n} for Region-{r} Contact-{c}".format(v=__VERSION__, n="Bigtopia",
                                                                                         r="Regionia", c="Blah")


# Integration Tests
class Test_Integration_NSAPI:
    @pytest.fixture
    def useragent(self):
        try:
            return ns.create_user_agent(contact_info=os.environ["CONTACT_INFO"], nation=os.environ["NATION"])
        except KeyError:
            raise EnvironmentError("You must provide CONTACT_INFO and NATION to run these tests!")

    @pytest.mark.asyncio
    async def test_get_nation(self, useragent):
        api = ns.NationStates_Client(user_agent=useragent, session=aiohttp.ClientSession())
        result = await api.get_nation("Testlandia", shards=None)
        assert result["NAME"] == "Testlandia"
        assert result["REGION"] == "Testregionia"
        assert len(result) > 2
        result = await api.get_nation("Testlandia", shards=["name", "region"])
        assert result["NAME"] == "Testlandia"
        assert result["REGION"] == "Testregionia"
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_region(self, useragent):
        api = ns.NationStates_Client(user_agent=useragent, session=aiohttp.ClientSession())
        result = await api.get_region("The Rejected Realms", shards=None)
        assert result["NAME"] == "the Rejected Realms"
        assert len(result) > 2
        assert len(result["EMBASSIES"]["EMBASSY"]) > 0
        api = ns.NationStates_Client(user_agent=useragent, session=aiohttp.ClientSession())
        result = await api.get_region("The Rejected Realms", shards=['name', 'embassies'])
        assert result["NAME"] == "the Rejected Realms"
        assert len(result) == 3
        assert len(result["EMBASSIES"]["EMBASSY"]) > 0

    @pytest.mark.asyncio
    async def test_get_world(self, useragent):
        api = ns.NationStates_Client(user_agent=useragent, session=aiohttp.ClientSession())
        result = await api.get_world(shards=["numnations", "featuredregion"])
        assert int(result["NUMNATIONS"]) > 1
        assert result["FEATUREDREGION"]
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_wa(self, useragent):
        api = ns.NationStates_Client(user_agent=useragent, session=aiohttp.ClientSession())
        result = await api.get_world_assembly(council_id=1, shards=["numnations", "numdelegates", "resolution"])
        assert int(result["NUMNATIONS"]) > 1
        assert int(result["NUMDELEGATES"]) > 1
        assert result["RESOLUTION"]
        assert result["RESOLUTION"]["CATEGORY"]
        assert len(result) == 4

    @pytest.mark.asyncio
    async def test_get_verify(self, useragent):
        api = ns.NationStates_Client(user_agent=useragent, session=aiohttp.ClientSession())
        result = await api.get_verify("testlandia", "abcdefgh1234567890")
        assert not result

    @pytest.mark.asyncio
    async def test_get_data_dump(self, useragent):
        api = ns.NationStates_Client(user_agent=useragent, session=aiohttp.ClientSession())
        result = await api.get_daily_dump("nations")
        assert not result


class Test_Integration_NSAPI_Dumps:

    @pytest.mark.asyncio
    async def test_get_nation(self):
        try:
            ua = ns.create_user_agent(contact_info=os.environ["CONTACT_INFO"], nation=os.environ["NATION"])
        except KeyError:
            raise EnvironmentError("You must provide CONTACT_INFO and NATION to run these tests!")

        api = ns.NationStates_Client(user_agent=ua, session=aiohttp.ClientSession())
        await api.get_daily_dump("nations")

        api = ns.NationStates_DataDump_Client()
        result = await api.get_nation("Testlandia", shards=None)
        assert result["NAME"] == "Testlandia"
        assert result["REGION"] == "Testregionia"
        assert len(result) > 2

        os.remove(api.nation_dump_file)

    @pytest.mark.asyncio
    async def test_get_region(self):
        try:
            ua = ns.create_user_agent(contact_info=os.environ["CONTACT_INFO"], nation=os.environ["NATION"])
        except KeyError:
            raise EnvironmentError("You must provide CONTACT_INFO and NATION to run these tests!")

        api = ns.NationStates_Client(user_agent=ua, session=aiohttp.ClientSession())
        await api.get_daily_dump("regions")

        api = ns.NationStates_DataDump_Client()
        result = await api.get_region("The Rejected Realms", shards=None)
        assert result["NAME"] == "the Rejected Realms"
        assert len(result) > 2
        assert len(result["EMBASSIES"]["EMBASSY"]) > 0

        os.remove(api.region_dump_file)

# Regression Tests
