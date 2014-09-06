from distutils.core import setup
setup(
    name='alphasms-client',
    version='0.1.1',
    description='Ukrainian AlphaSMS service client API implementation for Python',
    url='https://github.com/Obramko/python-alphasms-client',
    download_url='https://github.com/Obramko/python-alphasms-client/tarball/0.1.1',
    packages=['alphasms'],
    author='Vadym Abramchuk',
    author_email='abramm@gmail.com',
    maintainer='Vadym Abramchuk',
    maintainer_email='abramm@gmail.com',
    license='LGPLv3+',
    install_requires=[
        'requests'
    ],
    classifiers=[
        'Topic :: Communications :: Telephony',
        'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ]
)