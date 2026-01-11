FROM eclipse-temurin:21-jdk

WORKDIR /app

COPY . .

ARG DD_AGENT_VERSION=1.25.1
RUN curl -L -o dd-java-agent.jar \
    https://github.com/DataDog/dd-trace-java/releases/download/v${DD_AGENT_VERSION}/dd-java-agent.jar

RUN ./mvnw package -DskipTests

CMD ["java", "-javaagent:dd-java-agent.jar", "-jar", "target/spring-boot-demo-0.0.1-SNAPSHOT.jar"]


