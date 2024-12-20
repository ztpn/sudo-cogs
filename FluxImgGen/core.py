"""
MIT License

Copyright (c) 2023-present japandotorg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import io
import re
import random
from typing import Final, List, Optional
import aiohttp
import discord
from redbot.core import commands
from redbot.core.bot import Red

class DiffusionError(discord.errors.DiscordException):
    pass

class FluxImgGen(commands.Cog):
    __author__: Final[List[str]] = ["tpn"]
    __version__: Final[str] = "0.1.0"

    def __init__(self, bot: Red) -> None:
        self.bot: Red = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.model_mapping = {
            "base": "flux",
            "realism": "flux-realism",
            "3d": "flux-3d",
            "anime": "flux-anime",
            "disney": "flux-disney",
            "pixel": "flux-pixel",
            "4o": "flux-4o",
            "anydark": "any-dark",
            "pro": "flux.1.1-pro-ultra",
            "sd3": "stable-diffusion-3-large-turbo",
            "sdxl": "sdxl-lightning-4step",
            "kandinsky": "kandinsky-3.1",
            "deliberate3": "deliberate-v3",
            "rdxl": "realdream-xl",
            "jugg": "juggernaut-xl-v10",
            "half": "flux-half-illustration",
            "recraft": "recraft-v3",
        }

    async def initialize_tokens(self):
        self.tokens = await self.bot.get_shared_api_tokens("flux")
        if not self.tokens.get("model") or not self.tokens.get("size") or not self.tokens.get("endpoint") or not self.tokens.get("key"):
            raise DiffusionError("Setup not done. Use `set api flux key <api_key> set api flux model <default_model>`, `set api flux size <default_size>`, and `set api flux endpoint <baseUrl for api>`.")

    def format_help_for_context(self, ctx: commands.Context) -> str:
        pre_processed = super().format_help_for_context(ctx) or ""
        n = "\n" if "\n\n" not in pre_processed else ""
        text = [
            f"{pre_processed}{n}",
            f"Cog Version: **{self.__version__}**",
            f"Author: **{self.__author__}**",
        ]
        return "\n".join(text)

    async def cog_load(self) -> None:
        await self.initialize_tokens()

    async def cog_unload(self) -> None:
        if self.session:
            await self.session.close()

    async def _request(self, baseUrl: str, prompt: str, model: str, size: str) -> bytes:
        data = {
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "url",
            "model": model
        }
        
        key = self.tokens.get("key")
        headers = {
            "Authorization": f"Bearer {key}"
        }
        url = f"{baseUrl}/v1/images/generations"
        
        async with self.session.post(url, json=data, headers=headers) as response:
            content = await response.json()

            if not response.ok:
                raise DiffusionError(f"Error?: {response.status}")
            
            image_url = content["data"][0]["url"]
            async with self.session.get(image_url) as img_response:
                return await img_response.read()

    async def _generate_image(self, prompt: str, model: Optional[str], size: Optional[str]) -> bytes:
        default_model = self.tokens["model"]
        default_size = self.tokens["size"]
        baseUrl = self.tokens["endpoint"]

        size = size or default_size
        model = model or default_model
        if model.lower() not in self.model_mapping:
            raise DiffusionError(f"Model `{model}` does not exist.")
        model = self.model_mapping.get(model.lower(), model)
        return await self._request(baseUrl, prompt, model, size)

    async def _image_to_file(self, image_data: bytes, prompt: str) -> discord.File:
        return discord.File(
            io.BytesIO(image_data),
            filename=f"{prompt.replace(' ', '_')}.png"
        )

    @commands.command(name="flux", aliases=["f"])
    async def _gen(self, ctx: commands.Context, *, args: str) -> None:
        """
        **Arguments:**
        - `<prompt>` - A detailed description of the image you want to create.
        - `--model` - Choose the specific model to use for image generation.
        - `--size` - Resoultion for the generated image.
        
        **Models:**
        - `base` - Base flux model.
        - `realism` - Flux model with a LORa fine tuned for realism.
        - `3d` - Flux model with a LORa fine tuned for 3d images.
        - `anime` - Flux model with a LORa fine tuned for anime style.
        - `disney` - Flux model with a LORa fine tuned for disney style.
        - `pixel` - Flux model with a LORa fine tuned for pixelated style.
        - `4o` - Flux model with a LORa fine tuned for smth idk.
        - `anydark` - AnyDark model, great for dark scenes.
        - `pro` - FLux 1.1 Pro Ultra model.
        - `sd3` - Stable Diffusion 3 large turbo model.
        - `sdxl` - Stable Diffusion XL lightning model.
        - `kandinsky` - Kandinsky 3.1 model.
        - `deliberate3` - Deliberate v3 model.
        - `rdxl` - Realdream XL model.
        - `jugg` - Juggernaut XL v10 model.
        - `half` - Flux Half Illustration lora. Use "in the style of TOK" to trigger generation, creates half photo half illustrated elements.
        - `recraft` - Recraft V3.
        """
        await ctx.typing()
        args_list = args.split(" ")
        model = None
        size = None
        prompt_parts = []

        for arg in args_list:
            if arg.startswith("--model="):
                model = arg.split("=")[1]
            elif arg.startswith("--size="):
                size = arg.split("=")[1]
                if not re.match(r"^\d+x\d+$", size):
                    await ctx.send("Invalid size value. Please provide a valid resolution in the format 'width:height' (e.g., '1920x1080').")
                    return
            else:
                prompt_parts.append(arg)

        prompt = " ".join(prompt_parts)

        try:
            image_data = await self._generate_image(prompt, model, size)
        except DiffusionError as e:
            await ctx.send(
                f"Something went wrong...\n{e}",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
                allowed_mentions=discord.AllowedMentions(replied_user=False),
            )
            return
        except aiohttp.ClientResponseError as e:
            await ctx.send(
                f"Error?: `{e.status}`\n{e.message}",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
                allowed_mentions=discord.AllowedMentions(replied_user=False),
            )
            return
        file: discord.File = await self._image_to_file(image_data, prompt)
        await ctx.send(
            embed=discord.Embed(
                description=f"Prompt: {prompt}; Model: {model if model else self.tokens.get('model')};",
                color=await ctx.embed_color(),
            ),
            file=file,
        )