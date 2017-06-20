import requests
import yaml
from OpenSSL import SSL
from flask import Flask, render_template, flash, request, redirect, url_for, jsonify
from preston.esi import Preston

application = Flask(__name__)

names_url = 'https://esi.tech.ccp.is/latest/universe/names/?datasource=tranquility'

config = yaml.load(open('config.conf', 'r'))

application.config['SECRET_KEY'] = config['SECRET_KEY']
application.config['URL'] = config['URL']
application.config['SITE_NAME'] = config['SITE_NAME']

preston = Preston(
    user_agent=config['EVE_OAUTH_USER_AGENT'],
    client_id=config['EVE_OAUTH_CLIENT_ID'],
    client_secret=config['EVE_OAUTH_SECRET'],
    callback_url=config['EVE_OAUTH_CALLBACK'],
    scope=config['EVE_OAUTH_SCOPE']
)

trade_hub_system_ids = {
    'Amarr': 30002187,
    'Jita': 30000142,
    'Dodixie': 30002659,
    'Rens': 30002510,
    'Hek': 30002053
}

trade_hub_station_ids = {
    'Amarr': 60008494,
    'Jita': 60003760,
    'Dodixie': 60011866,
    'Rens': 60004588,
    'Hek': 60005686
}


@application.route('/traderouter')
@application.route('/traderouter/')
def landing():
    return render_template('index.html', show_crest=True, crest_url=preston.get_authorize_url())


@application.route('/traderouter/router')
@application.route('/traderouter/router/<refresh_token>')
@application.route('/traderouter/router/<refresh_token>/')
def router(refresh_token=None):
    try:
        if refresh_token is None:
            # check response
            if 'error' in request.path:
                flash('There was an error in EVE\'s response', 'error')
                return redirect(url_for('router'))

            try:
                auth = preston.authenticate(request.args['code'])
            except Exception as e:
                print('SSO callback exception: ' + str(e))
                flash('There was an error signing you in.', 'error')
                return redirect(url_for('landing'))

            return redirect(url_for('router', refresh_token=auth.refresh_token))

        else:
            auth = preston.use_refresh_token(refresh_token)
            pilot_info = auth.whoami()
            pilot_name = pilot_info['CharacterName']
            pilot_id = pilot_info['CharacterID']

            location = auth.characters[pilot_id].location()
            system_id = location['solar_system_id']

            distances = {}
            for name, th_id in trade_hub_system_ids.items():
                route = preston.route[system_id][th_id]()
                distances[name] = {
                    'distance': len(route) - 1,
                    'system_id': th_id,
                    'station_id': trade_hub_station_ids[name]
                }

            current_system = requests.post(url=names_url, json=[system_id]).json()[0]['name']

    except Exception as e:
        flash('There was an error: ' + str(e), 'error')
        print('Error: ' + str(e))
        return redirect(url_for('landing'))

    return render_template('index.html', show_crest=False, pilot_name=pilot_name, pilot_id=pilot_id,
                           current_system=current_system, current_id=system_id, distances=distances,
                           token=auth.access_token, refresh_token=refresh_token)


@application.route('/traderouter/search/<system_name>')
def search(system_name):
    system_id = requests.get(
        url="https://esi.tech.ccp.is/latest/search/?categories=solarsystem&datasource=tranquility&language=en-us&strict=true&search=" + system_name
    ).json()['solarsystem'][0]

    distances = {}
    for name, th_id in trade_hub_system_ids.items():
        route = preston.route[system_id][th_id]()
        distances[name] = {
            'distance': len(route) - 1,
            'system_id': th_id,
            'station_id': trade_hub_station_ids[name]
        }

    return jsonify(distances)

@application.route('/traderouter/update/<action>/<refresh_token>')
def update(action, refresh_token):
    try:
        auth = preston.use_refresh_token(refresh_token)
        pilot_info = auth.whoami()
        pilot_name = pilot_info['CharacterName']
        pilot_id = pilot_info['CharacterID']

        location = auth.characters[pilot_id].location()
        system_id = location['solar_system_id']
        current_system = requests.post(url=names_url, json=[system_id]).json()[0]['name']

        if action == 'location':
            location = {
                'name': current_system,
                'system_id': system_id
            }
            return jsonify(location)

        elif action == 'distances':
            distances = {}
            for name, th_id in trade_hub_system_ids.items():
                route = preston.route[system_id][th_id]()
                distances[name] = {
                    'distance': len(route) - 1,
                    'system_id': th_id,
                    'station_id': trade_hub_station_ids[name]
                }

            distances['current'] = {
                'name': current_system,
                'system_id': system_id
            }

            return jsonify(distances)

    except Exception as e:
        flash('There was an error: ' + str(e), 'error')
        print('Error: ' + str(e))
        return redirect(url_for('landing'))


if __name__ == "__main__":
    application.run(host='0.0.0.0', debug=True, ssl_context='adhoc')
