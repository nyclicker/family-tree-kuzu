const { execSync } = require('child_process');

module.exports = async () => {
  console.log('Tearing down Docker containers...');
  try {
    execSync('docker-compose down', { stdio: 'inherit' });
    console.log('Docker containers stopped successfully');
  } catch (error) {
    console.error('Error stopping Docker containers:', error.message);
  }
};
