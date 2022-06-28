# Warranty / End of Life Support
# Tech Vigilantes
# 2022 Digital KickOff

Project Video: https://www.youtube.com/watch?v=RHOhHXcPZQc

## Summary
The project's goal is to grab warranty, end of life, and support contract dates 
for devices inside a ServiceNow instance. So far, it will only grab this 
information for Cisco and Dell devices, however, in the future we plan on 
supporting other manufacturers. The data grabbed is then displayed in a custom
ServiceNow dashboard which is able to give a user an insight on their customer's
warranty and end of life statuses for all their devices.

_Note: If you have any questions or comments you can always use GitHub
discussions, or email me at farinaanthony96@gmail.com._

#### Why
The information that is pushed into ServiceNow is vital to helping the user
get an idea for the status of their device's support. A user is able to make
a more informed decision on how many devices need new warranties. They are also
able to detect if a device is obsolete using their end of life date. This is
valuable for customers to know so they can buy new devices that are supported
to keep their environments free of out-of-date hardware.

## Requirements
- Python >= 3.10.4
- configparser >= 5.2.0
- oauthlib >= 3.2.0
- requests-oauthlib >= 1.3.1

## Usage
- Edit the config file with ServiceNow instance information, Cisco API access
  information, and Dell API access information.

- Simply run the script using Python:
  `python 2022-DIKO-Project.py`

## Compatibility
Should be able to run on any machine with a Python interpreter. This script
was only tested on a Windows machine running Python 3.10.4.

## Disclaimer
The code provided in this project is an open source example and should not
be treated as an officially supported product. Use at your own risk. If you
encounter any problems, please log an
[issue](https://github.com/CC-Digital-Innovation/2022-DIKO-Project/issues).

## Contributing
1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request ツ

## History
- version 1.0.0 - 2022/06/28
    - (initial release)

## Credits
Anthony Farina <<farinaanthony96@gmail.com>>
