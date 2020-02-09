"""

"""
import logging
from io import BytesIO
from functools import partial
from typing import Optional, Union, List, Dict, Tuple

import aiohttp
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
import discord
from discord.ext import commands

# noinspection PyUnresolvedReferences
import imgUtils.roundedRect  # Monkey patch the roundedRect method into PIL

log = logging.getLogger(__name__)
discord_dark_mode_bg = (54, 57, 63)


async def get_avatar_changed_image(bot: commands.bot, before: discord.User, after: discord.User, avatar_info) -> BytesIO:

    # Get the avatars as a sequence of bytes
    avatar_bytes_b = await get_avatar(before)
    avatar_bytes_a = await get_avatar(after)

    # create partial function so we don't have to stack the args in run_in_executor
    fn = partial(avatar_changed_processor_trans_bg, avatar_bytes_b, avatar_bytes_a, avatar_info)

    # this runs our processing in an executor, stopping it from blocking the thread loop.
    # as we already seeked back the buffer in the other thread, we're good to go
    final_img_buffer = await bot.loop.run_in_executor(None, fn)

    return final_img_buffer


async def get_avatar(user: Union[discord.User, discord.Member]) -> Optional[bytes]:
    # generally an avatar will be 1024x1024, but we shouldn't rely on this
    avatar_url = str(user.avatar_url_as(format="png"))

    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as response:
            if response.status == 200:
                # this gives us our response object, and now we can read the bytes from it.
                avatar_bytes = await response.read()
            elif response.status == 404:
                avatar_bytes = None
                log.warning("Got 404 trying to download pfp!")
            else:
                avatar_bytes = None
                log.error(f"Got {response.status} trying to download pfp!\n{response}")
    return avatar_bytes


def open_and_prepare_avatar(image_bytes: Optional[bytes]) -> Optional[Image.Image]:
    """Opens the image as bytes if they exist, otherwise opens the 404 error image. then circular crops and resizes it"""
    if image_bytes is not None:
        try:
            with Image.open(BytesIO(image_bytes)) as im:
                prepared_image = crop_circular_border_w_transparent_bg(im)
                prepared_image = resize_image(prepared_image)
        except UnidentifiedImageError as e:
            log.error("Error loading Avatar", exc_info=e)
            return None
    else:
        with Image.open("resources/404 Avatar Not Found.png") as im:
            prepared_image = crop_circular_border_w_transparent_bg(im)
            prepared_image = resize_image(prepared_image)

    return prepared_image


def avatar_changed_processor_trans_bg(before_avatar_bytes: Optional[bytes], after_avatar_bytes: Optional[bytes], avatar_info) -> Optional[BytesIO]:
    # we must use BytesIO to load the image here as PIL expects a stream instead of
    # just raw bytes.
    b_avatar = open_and_prepare_avatar(before_avatar_bytes)
    a_avatar = open_and_prepare_avatar(after_avatar_bytes)
    if b_avatar is None or a_avatar is None:
        log.error(f"Avatar info: {avatar_info}")
        return None

    text_box_height = 60
    image_spacing = 25
    sbs_image_size = (a_avatar.width * 2 + image_spacing, a_avatar.height + text_box_height)
    sbs_background_color = (0, 0, 0, 0)  # discord_dark_mode_bg  # (250, 250, 250)

    with Image.new("RGBA", sbs_image_size, sbs_background_color) as sbs:
        # sbs.paste(a_avatar, (0, text_box_height), a_avatar)
        # sbs.paste(b_avatar, (a_avatar.width + 25, text_box_height), b_avatar)
        sbs.alpha_composite(b_avatar, (0, text_box_height))
        sbs.alpha_composite(a_avatar, (b_avatar.width + image_spacing, text_box_height))

    # sbs = add_avatar_changed_text(sbs, (a_avatar.width//2, 50))

    text_horiz_offset = 0

    old_avatar_text_pos = (b_avatar.width // 2, (text_box_height // 2) + text_horiz_offset)
    new_avatar_text_pos = ((a_avatar.width // 2) + b_avatar.width + image_spacing, (text_box_height // 2) + text_horiz_offset)

    old_avatar_text = "Old Avatar"
    new_avatar_text = "New Avatar"
    side_ellipse_margin = 10
    top_bottom_ellipse_margin = -5

    sbs = add_text_w_bg(old_avatar_text, sbs, old_avatar_text_pos, side_ellipse_margin, top_bottom_ellipse_margin)
    sbs = add_text_w_bg(new_avatar_text, sbs, new_avatar_text_pos, side_ellipse_margin, top_bottom_ellipse_margin)

    final_image = get_image_buffer(sbs)
    return final_image


def add_rounded_rect(image: Image.Image, center_pos: Tuple[int, int], width: int, height: int) -> Image.Image:

    fill = (60, 0, 125)#(47, 49, 54, 255)
    radius = 20
    bottom_offset = 8

    top_corner_x = center_pos[0] - (width//2)
    top_corner_y = center_pos[1] - (height // 2)
    bottom_corner_x = center_pos[0] + (width // 2)
    bottom_corner_y = center_pos[1] + (height // 2) + bottom_offset

    position = (top_corner_x, top_corner_y), (bottom_corner_x, bottom_corner_y)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(position, corner_radius=radius, fill=fill)

    return image


def add_text_w_bg(text: str, img: Image.Image, pos: Tuple[int, int], side_bg_margin: int, top_bottom_bg_margin: int) -> Image.Image:

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype('resources/Roboto-Bold.ttf', size=45)
    text_color = (224, 224, 224)  # (0,0,0)#

    msg = text
    centered_pos = center_text(msg, pos[0], pos[1], font)

    text_x, text_y = font.getsize(text)

    img = add_rounded_rect(img, pos, text_x + (side_bg_margin * 2), text_y + (top_bottom_bg_margin * 2))

    draw.text(centered_pos, msg, fill=text_color, font=font)

    return img


def add_text(text: str, img: Image.Image, pos: Tuple[int, int]) -> Image.Image:

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype('Roboto-Bold.ttf', size=45)
    text_color = (224, 224, 224)  # (0,0,0)#

    msg = text
    centered_pos = center_text(msg, pos[0], pos[1], font)

    draw.text(centered_pos, msg, fill=text_color, font=font)

    return img


def center_text(text: str, x_pos: int, y_pos: int, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:

    text_x, text_y = font.getsize(text)

    x = (x_pos - text_x//2)  # / 2
    y = (y_pos - text_y//2)  # / 2

    return x, y


def crop_circular_border_w_transparent_bg(avatar: Image.Image) -> Image.Image:
    color = (0, 0, 0, 0)
    with Image.new("RGBA", avatar.size, color) as background:
        # this ensures that the user's avatar lacks an alpha channel, as we're
        # going to be substituting our own here.

        # Actually lets keep the Alpha channel by making it RGBA instead of RGB
        rgb_avatar = avatar.convert("RGBA")

        # this is the mask image we will be using to create the circle cutout
        # effect on the avatar.
        with Image.new("L", avatar.size, 0) as mask:
            # ImageDraw lets us draw on the image, in this instance, we will be
            # using it to draw a white circle on the mask image.
            mask_draw = ImageDraw.Draw(mask)

            # draw the white circle from 0, 0 to the bottom right corner of the image
            mask_draw.ellipse([(0, 0), avatar.size], fill=255)

            # # paste the alpha-less avatar on the background using the new circle mask
            # # we just created.
            background.paste(rgb_avatar, (0, 0), mask=mask)

    return background


def get_image_buffer(img: Image.Image) -> BytesIO:
    # prepare the stream to save this image into
    final_buffer = BytesIO()

    # save into the stream, using png format.
    img.save(final_buffer, "png")

    # seek back to the start of the stream
    final_buffer.seek(0)

    return final_buffer


def resize_image(avatar: Image.Image, size: Tuple[int] = (512, 512)) -> Image.Image:
    """Resize the image. Defaults to a 512x512 size."""
    """
    Resizing Algorithms:
    https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters-comparison-table
    HAMMING: If we only want to downscale this might be the best trade off between speed and quality.
    """
    resizeing_algorithm = Image.HAMMING
    return avatar.resize(size, resample=resizeing_algorithm)


def image_processing(avatar_bytes: bytes, colour: tuple) -> BytesIO:
    """This method is to be run in an executor"""

    # we must use BytesIO to load the image here as PIL expects a stream instead of
    # just raw bytes.
    with Image.open(BytesIO(avatar_bytes)) as im:
        log.info(f"pfp info: size(w,h) {im.size}, format: {im.format}")
        # this creates a new image the same size as the user's avatar, with the
        # background colour being the user's colour.
        # with Image.new("RGBA", im.size, colour) as background:

        with Image.new("RGBA", im.size, (54, 57, 63, 255)) as background: # colour # (54, 57, 63, 0)  #(0, 0, 0, 0) makes full transp

            # this ensures that the user's avatar lacks an alpha channel, as we're
            # going to be substituting our own here.
            rgb_avatar = im.convert("RGBA")

            background.paste(rgb_avatar, mask=rgb_avatar)
            # this is the mask image we will be using to create the circle cutout
            # effect on the avatar.
            with Image.new("L", im.size, 0) as mask:
                # ImageDraw lets us draw on the image, in this instance, we will be
                # using it to draw a white circle on the mask image.
                mask_draw = ImageDraw.Draw(mask)

                # draw the white circle from 0, 0 to the bottom right corner of the image
                mask_draw.ellipse([(0, 0), im.size], fill=255)

                # paste the alpha-less avatar on the background using the new circle mask
                # we just created.
                # background.paste(rgb_avatar, (0, 0), mask=mask)
                background.putalpha(mask)


            # prepare the stream to save this image into
            final_buffer = BytesIO()

            # save into the stream, using png format.
            background.save(final_buffer, "png")

    # seek back to the start of the stream
    final_buffer.seek(0)

    return final_buffer

