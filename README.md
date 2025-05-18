# Digital Voting System

A secure and transparent platform for democratic elections built with Flask,Javascript,SQLAlchemy, PostgreSQL, HTML/CSS, Bootstrap, JWT, UUID

![Picture 1](https://github.com/khyatikss/Digital-voting-system/blob/main/Picture1.png?raw=true)


## Features

- User (voter) and admin authentication
- Candidate management with profiles and images
- Election creation and management
- Secure voting with confirmation codes
- Real-time results dashboard for admins
- Responsive UI design

## Installation

### Using Docker (Recommended)

1. Make sure you have Docker and Docker Compose installed
2. Clone this repository
3. Navigate to the project directory
4. Run the application with Docker Compose:

```bash
docker-compose up -d
```

5. Access the application at http://localhost:5000

### Manual Installation

1. Clone this repository
2. Create a virtual environment:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
3. Install dependencies:
```
pip install -r requirements.txt
```
4. Run the application:
```
flask run
```
5. Access the application at http://localhost:5000

## Default Admin Account
- Username: admin
- Password: admin123
  
## RESULTS
  
![Image 1](https://github.com/khyatikss/Digital-voting-system/blob/main/Picture2.png?raw=true)

![Image 2](https://github.com/khyatikss/Digital-voting-system/blob/main/Picture5.png?raw=true)

![Image 3](https://github.com/khyatikss/Digital-voting-system/blob/main/Picture4.png?raw=true)

![Image 4](https://github.com/khyatikss/Digital-voting-system/blob/main/Picture6.png?raw=true)

![Image 5](https://github.com/khyatikss/Digital-voting-system/blob/main/Picture3.png?raw=true)


## Usage
1. Register as a voter or login with the admin account
2. Admin can add candidates and create elections
3. Voters can cast their votes for available candidates
4. Voters receive a confirmation code after voting
5. Admin can view real-time election results

## License
This project is licensed under the MIT License - see the LICENSE file for details.
