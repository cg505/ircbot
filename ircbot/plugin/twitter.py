"""Post the contents of linked tweets."""
import requests
from functools import lru_cache

API = 'https://api.twitter.com'


def register(bot):
    bot.listen(r'https?://(?:mobile\.|www\.|m\.)?twitter\.com/[^/]+/status/([0-9]+)', show_tweet)


@lru_cache(maxsize=1)
def _get_token(apikeys):
    resp = requests.post(
        '{}/oauth2/token'.format(API),
        data={'grant_type': 'client_credentials'},
        auth=apikeys,
    )
    resp.raise_for_status()

    authorization = resp.json()
    assert authorization['token_type'] == 'bearer'
    return authorization['access_token']


def _get_tweet(apikeys, status_id, retry=True):
    bearer_token = _get_token(apikeys)

    resp = requests.get('{}/1.1/statuses/show.json?id={}&tweet_mode=extended'.format(
        API,
        status_id,
    ), headers={
        'Authorization': 'Bearer {}'.format(bearer_token),
    })
    if resp.status_code == 404:
        return None
    if resp.status_code == 401 and retry:
        _get_token.cache_clear()
        # make sure not to get stuck in an infinite loop of 401s
        return _get_tweet(apikeys, status_id, False)
    resp.raise_for_status()

    return resp.json()


def _format_media(media, url):
    media_urls = [medium['media_url_https']
                  for medium in media if medium['type'] == 'photo']
    if any([medium['type'] != 'photo' for medium in media]):
        media_urls += [url]
    return ' '.join(media_urls)


def _format_tweet(tweet):
    contents = tweet['full_text']
    media = tweet.get('extended_entities', {}).get('media')
    if media:
        # url is the same for all media
        url = media[0]['url']
        contents = contents.replace(
            url,
            _format_media(media, url),
        )
    contents = contents.replace('\n', ' ')
    return '@{handle} ({realname}): {contents}'.format(
        handle=tweet['user']['screen_name'],
        realname=tweet['user']['name'],
        contents=contents,
    )


def show_tweet(bot, msg):
    """Show tweet content."""
    tweet = _get_tweet(bot.twitter_apikeys, msg.match.group(1))
    if tweet:
        print(_format_tweet(tweet))
        msg.respond(_format_tweet(tweet), ping=False)
