library 'sp-jenkins'

pipeline {
  agent any
  environment {
    BUILD_WORKDIR = "/tmp/${env.BUILD_TAG}/"
  }
  stages {
    stage('build') {
      when {
        anyOf {
          branch 'master'
          branch 'production'
          branch 'release_candidate'
          changeRequest title: ".*JENKINSFILE_TESTING.*", comparator: 'REGEXP'
          buildingTag()
        }
      }
          steps {
            publishWheels codeBuildEnv: '[ { RUN_TESTS, false },{ pip_version, pip3.8 } ]'
          }
    }
  }
  post {
    cleanup {
      echo "Deleting working directory ${env.BUILD_WORKDIR}"
      sh 'rm -rf $BUILD_WORKDIR'
    }
    always {
      buildNotification()
    }
  }
}
