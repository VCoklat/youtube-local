import flask

from youtube import yt_app


@yt_app.route('/facebook')
@yt_app.route('/facebook/<path:subpath>')
def facebook_placeholder_page(subpath=''):
    return (
        flask.render_template(
            'error.html',
            error_message=(
                'Facebook-Local is not implemented yet in this build.'
            ),
            slim=False,
        ),
        501,
    )
