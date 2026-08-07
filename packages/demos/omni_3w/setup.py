from setuptools import setup

package_name = 'omni_3w'
setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/sim.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Lappa',
    maintainer_email='lappa@mergeos.shop',
    description='Holonomic 3-wheel omnidirectional base',
    license='MIT',
    entry_points={'console_scripts': ['teleop = omni_3w.teleop:main']},
)
