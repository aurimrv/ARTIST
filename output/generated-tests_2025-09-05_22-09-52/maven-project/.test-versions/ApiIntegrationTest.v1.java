package org.javiermf.features.models.tests;

import org.junit.Before;
import org.junit.Test;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import static org.junit.Assert.*;
import static org.hamcrest.Matchers.*;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;
import static io.restassured.RestAssured.*;
import io.restassured.http.ContentType;

public class ApiIntegrationTest {

    private static final String BASE_URL = "http://localhost:8080";
    private static final int DEFAULT_TIMEOUT = 30;

    @BeforeClass
    public static void setUpClass() {
        RestAssured.baseURI = BASE_URL;
        RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();
    }

    @AfterClass
    public static void tearDownClass() {
        RestAssured.reset();
    }

    @Before
    public void setUp() {
        createInitialData();
    }

    @After
    public void tearDown() {
        deleteAllData();
    }

    @Test
    public void testCreateProduct() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .body("{\"productName\": \"TestProduct\"}")
        .when()
            .post("/products/{productName}")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testRetrieveProduct() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
        .when()
            .get("/products/{productName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testAddFeatureToProduct() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .pathParam("featureName", "TestFeature")
            .body("{\"featureName\": \"TestFeature\", \"description\": \"A test feature\"}")
        .when()
            .post("/products/{productName}/features/{featureName}")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testUpdateFeatureDescription() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .pathParam("featureName", "TestFeature")
            .body("{\"description\": \"Updated test feature\"}")
        .when()
            .put("/products/{productName}/features/{featureName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testCreateConfiguration() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .pathParam("configurationName", "TestConfig")
            .body("{\"configurationName\": \"TestConfig\"}")
        .when()
            .post("/products/{productName}/configurations/{configurationName}")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testAddFeatureToConfiguration() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .pathParam("configurationName", "TestConfig")
            .pathParam("featureName", "TestFeature")
        .when()
            .post("/products/{productName}/configurations/{configurationName}/features/{featureName}")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testRemoveFeatureFromConfiguration() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .pathParam("configurationName", "TestConfig")
            .pathParam("featureName", "TestFeature")
        .when()
            .delete("/products/{productName}/configurations/{configurationName}/features/{featureName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testDeleteFeatureFromProduct() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .pathParam("featureName", "TestFeature")
        .when()
            .delete("/products/{productName}/features/{featureName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testDeleteProduct() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "TestProduct")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    private RequestSpecification givenDefaultRequest() {
        return given()
            .contentType(ContentType.JSON)
            .accept(ContentType.JSON);
    }

    private void validateResponseTime(Response response) {
        response.then().time(lessThan((long) DEFAULT_TIMEOUT * 1000));
    }

    private void validateJsonResponse(Response response) {
        response.then().contentType(ContentType.JSON);
    }

    private void createInitialData() {
        givenDefaultRequest()
            .pathParam("productName", "TestProduct")
            .body("{\"productName\": \"TestProduct\"}")
        .when()
            .post("/products/{productName}")
        .then()
            .statusCode(201);
    }

    private void deleteAllData() {
        givenDefaultRequest()
            .pathParam("productName", "TestProduct")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(200);
    }
}