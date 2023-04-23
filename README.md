# Nerris Bot
  Nerris is an Open Source Discord Bot written in Python 3, primarily for The Campfire Discord server.
This bot mainly performs certain actions -- such as NationStates verification and aims to be complete, but fast.

## Features
- NationStates Verification


## Requirements
- Python 3.11 or greater
- discord.py v2.0
- aiohttp v3.8
- aiodns v3.0
- SQLAlchemy v2.0

## Quick Start
To quickly get started with Nerris, you first need to register a bot with discord and get the API Key. After that,
you can take `default_config.toml` and create a copy named `nerris.toml` and put the API key in the config file. 

After that, you need to fill out the config file for use, and then simply install the package with `python -m pip install .`.
You can then start Nerris with `python3 -m Nerris.nerris`. 

For a more 'robust' setup please see the documentation.

## Development Setup
To simplify this you can just do `pip install -e .[dev]` and it will install the development dependencies, without
strict pinning. If you wish you can use the frozen requirements.txt to ensure compatibability if you run into issues.

# License and Copyright
All authors retain their copyright in this work unless otherwise specified.

The source code within this repository is licensed under the AGPL v3 license,
all non-code work is licensed under the CC-BY-NC-SA 4.0 License as well.

# QnA/FaQ
### What's with the name "Nerris"?  
Nerris is a character off of the show Camp Camp produced by Rooster Teeth. I particularly like Nerris as a character,
and given that the alternatives weren't really that great, and that the character fit the theme of The Campfire, I chose
it because no one could get behind a singular name.

### Why not use Poetry?  
Because it doesn't follow the standards as set forth by the various PEPs around packaging. When it does, I'll consider it.

### Why do you have a `setup.cfg` file? Why not just put it all in the `pyproject.toml` file?  
It is because, unfortunately, setuptools has not stabilized everything I would need for the `pyproject.toml` file to work
for our use-case. While it may be the case that it is perfectly stable and won't change, I don't have a guarantee and
I do not want to deal with that. So I have a `setup.cfg` file for now. Once they do stabilize the features I would need,
I will gladly switch to a singular `pyproject.toml` file.

### Should I use this?  
If this meets your needs! This bot is not for everyone, and currently only really does one thing: "NS Verification"
and giving roles based upon that verification. That's about it. 

However, if the current bot(s) to do NationStates verification aren't really up to snuff for you, and you're potentially
fine with self-hosting, feel free to use Nerris and also to contribute!

### Should I use this over X?  
At the moment, probably not. While most things are stable, the bot is still in a very early state and there are some potential
bugs and other issues that could arise. As such I would recommend using those bots if you're not able to really do much with
the code.

### Why do you not have feature X/Y/Z?  
Because the bot is currently under heavy development. Also the initial version is more of a 'Minimum Viable Product' in a sense.
It's a relatively basic implementation of what is needed specifically for 'The Campfire' and nothing more. I do intend on adding
more features over-time, however we have to start somewhere.

If you see a feature you need, and want to use Nerris feel free to request it, just keep in mind it might not happen right away,
that is unless you also wish to submit a PR for that feature.

### Why is this project open sourced?  
Because all the other relevant bots are private and closed-source (at least, to my knowledge). I do not want to forever be
tasked with the maintanance of this bot -- or seeking out a maintainer when I decide I want to retire from development. I also
believe that is to the benefit of all players, of all regions, in NationStates to open source technology that a region relies on,
not just for transparancy but also for data ownership. So this project was always going to be open source.

### Why did is this licensed under the AGPL v3?  
Because it was either this, the GPL v3, or the MIT License. I decided to go with the AGPL v3 for a few reasons.

The first was pretty simple, once I make the source available there's no strict going back. If I made the source initially
licensed under the MIT License, but then wanted to switch the AGPL v3, then someone could just fork from the MIT license 
and continue it. That would be reasonable, and certainly their right, but it would render a switch to that license effectively
dead on arrival. In order to prevent that I would need to remove each and every online copy of the bot's source, which isn't
feasable nor possible and I wouldn't want to do that. However going the other way is relatively easy, in terms of 'control'.

The next is also pretty simple, if all my competitors are closed sourced bots, what to stop them from using my code (assuming they
are written in Python which, I'm not certain of) to improve their bot? While I don't (currently) have anything they would
be likely to use, in the future that may not be the case. It's doubtful, but a concerning possibility for me none-the-less as
them doing that would defeat my desire for more openness on NationStates on this front. With this in mind, I only had two licenses:
GPL and the AGPL.

As to why the AGPL vs the GPL, this is a Discord bot. It's entirely provided 'as a service' to Discord Users. As such, it is my
understanding that the conditions of the GPL don't necesarily trigger or require 'sharing' of their code. This would effectively
allow them to close source the bot and make 'improvements' without contributing back to everyone. This would be effectively
the same circumstances under the last reason -- but also means that I make their bot better and they do nothing for everyone else.
In my opinion this is a problem as it robs users of the ability to make improvements to that bot and also robs everyone else using
that bot from the benefits of your improvements. However, the AGPL does trigger under these circumstances and require sharing.
As such it was the best option to achieve what my goals, while also being open. 

This is not to say I will never change the license or dual license or what have you. It is just that, at this time, the
purposes for me open sourcing and making this bot available means that the best tool to do that is the AGPL v3. I may very well
decide to try to relicense this in the future, and if I do it will likely be to change it to something like the MIT License.
If the AGPL v3 is truely intolerable to you, and you still want to use this bot, and I'm willing to work with you (since I am
the only copyright holder and author. This will obviously change in the future though).
