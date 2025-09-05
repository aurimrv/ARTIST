package org.javiermf.features.models.tests;

import org.junit.Before;
import org.junit.Test;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import org.junit.Ignore;
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
        populateDatabase();
    }

    @After
    public void tearDown() {
        clearDatabase();
    }

    @Test
    public void test_get_products_success() {
        Response response = givenDefaultRequest()
        .when()
            .get("/products")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_post_products_productName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "smartphone")
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
    public void test_get_products_productName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
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
    public void test_get_products_productName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
        .when()
            .get("/products/{productName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop-pro-15")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_get_products_productName_features_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "smartphone")
        .when()
            .get("/products/{productName}/features")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_get_products_productName_features_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
        .when()
            .get("/products/{productName}/features")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_post_products_productName_features_featureName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .pathParam("featureName", "dark-mode")
            .queryParam("description", "Provides")
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
    public void test_post_products_productName_features_featureName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("featureName", "NonExistent")
            .queryParam("description", "NonExistent")
        .when()
            .post("/products/{productName}/features/{featureName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_put_products_productName_features_featureName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .pathParam("featureName", "color")
            .queryParam("description", "Enhanced")
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
    public void test_put_products_productName_features_featureName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("featureName", "NonExistent")
            .queryParam("description", "NonExistent")
        .when()
            .put("/products/{productName}/features/{featureName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_features_featureName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "smartphone")
            .pathParam("featureName", "darkMode")
        .when()
            .delete("/products/{productName}/features/{featureName}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_features_featureName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("featureName", "NonExistent")
        .when()
            .delete("/products/{productName}/features/{featureName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_get_products_productName_configurations_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
        .when()
            .get("/products/{productName}/configurations")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_get_products_productName_configurations_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
        .when()
            .get("/products/{productName}/configurations")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_post_products_productName_configurations_configurationName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .pathParam("configurationName", "us-east-1")
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
    public void test_post_products_productName_configurations_configurationName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("configurationName", "NonExistent")
        .when()
            .post("/products/{productName}/configurations/{configurationName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .pathParam("configurationName", "us-east-1")
        .when()
            .get("/products/{productName}/configurations/{configurationName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("configurationName", "NonExistent")
        .when()
            .get("/products/{productName}/configurations/{configurationName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .pathParam("configurationName", "us-east-1")
        .when()
            .delete("/products/{productName}/configurations/{configurationName}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("configurationName", "NonExistent")
        .when()
            .delete("/products/{productName}/configurations/{configurationName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_features_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .pathParam("configurationName", "standard-configuration")
        .when()
            .get("/products/{productName}/configurations/{configurationName}/features")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_features_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("configurationName", "NonExistent")
        .when()
            .get("/products/{productName}/configurations/{configurationName}/features")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_post_products_productName_configurations_configurationName_features_featureName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "smartphone")
            .pathParam("configurationName", "standard")
            .pathParam("featureName", "darkMode")
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
    public void test_post_products_productName_configurations_configurationName_features_featureName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("configurationName", "NonExistent")
            .pathParam("featureName", "NonExistent")
        .when()
            .post("/products/{productName}/configurations/{configurationName}/features/{featureName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_features_featureName_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "smartphone")
            .pathParam("configurationName", "standard")
            .pathParam("featureName", "darkMode")
        .when()
            .delete("/products/{productName}/configurations/{configurationName}/features/{featureName}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_features_featureName_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("configurationName", "NonExistent")
            .pathParam("featureName", "NonExistent")
        .when()
            .delete("/products/{productName}/configurations/{configurationName}/features/{featureName}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_post_products_productName_constraints_requires_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .queryParam("sourceFeature", "authentication")
            .queryParam("requiredFeature", "authentication")
        .when()
            .post("/products/{productName}/constraints/requires")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_post_products_productName_constraints_requires_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .queryParam("sourceFeature", "NonExistent")
            .queryParam("requiredFeature", "NonExistent")
        .when()
            .post("/products/{productName}/constraints/requires")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_post_products_productName_constraints_excludes_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .queryParam("sourceFeature", "us")
            .queryParam("excludedFeature", "discount")
        .when()
            .post("/products/{productName}/constraints/excludes")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_post_products_productName_constraints_excludes_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .queryParam("sourceFeature", "NonExistent")
            .queryParam("excludedFeature", "NonExistent")
        .when()
            .post("/products/{productName}/constraints/excludes")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_constraints_constraintId_success() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "laptop")
            .pathParam("constraintId", "123")
        .when()
            .delete("/products/{productName}/constraints/{constraintId}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_delete_products_productName_constraints_constraintId_not_found() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "NonExistent")
            .pathParam("constraintId", "NonExistent")
        .when()
            .delete("/products/{productName}/constraints/{constraintId}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_get_root_source_code() {
        Response response = givenDefaultRequest()
        .when()
            .get("/")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_get_configurationName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("configurationName", "test")
        .when()
            .get("/{configurationName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_post_configurationName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("configurationName", "test")
        .when()
            .post("/{configurationName}")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_delete_configurationName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("configurationName", "test")
        .when()
            .delete("/{configurationName}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_get_products_source_code() {
        Response response = givenDefaultRequest()
        .when()
            .get("/products")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_get_products_productName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "test")
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
    public void test_delete_products_productName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "test")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_post_products_productName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("productName", "test")
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
    public void test_post_featureName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("featureName", "test")
        .when()
            .post("/{featureName}")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_delete_featureName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("featureName", "test")
        .when()
            .delete("/{featureName}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void test_put_featureName_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("featureName", "test")
        .when()
            .put("/{featureName}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_post_requires_source_code() {
        Response response = givenDefaultRequest()
        .when()
            .post("/requires")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_post_excludes_source_code() {
        Response response = givenDefaultRequest()
        .when()
            .post("/excludes")
        .then()
            .statusCode(201)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();

        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void test_delete_constraintId_source_code() {
        Response response = givenDefaultRequest()
            .pathParam("constraintId", "1")
        .when()
            .delete("/{constraintId}")
        .then()
            .statusCode(204)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
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

    private void populateDatabase() {
        givenDefaultRequest()
            .pathParam("productName", "laptop")
        .when()
            .post("/products/{productName}")
        .then()
            .statusCode(201);

        givenDefaultRequest()
            .pathParam("productName", "smartphone")
        .when()
            .post("/products/{productName}")
        .then()
            .statusCode(201);

        givenDefaultRequest()
            .pathParam("productName", "laptop-pro-15")
        .when()
            .post("/products/{productName}")
        .then()
            .statusCode(201);
    }

    private void clearDatabase() {
        givenDefaultRequest()
            .pathParam("productName", "laptop")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(204);

        givenDefaultRequest()
            .pathParam("productName", "smartphone")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(204);

        givenDefaultRequest()
            .pathParam("productName", "laptop-pro-15")
        .when()
            .delete("/products/{productName}")
        .then()
            .statusCode(204);
    }
}