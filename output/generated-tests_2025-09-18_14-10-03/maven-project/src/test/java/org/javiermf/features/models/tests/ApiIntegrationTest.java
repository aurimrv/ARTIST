package org.javiermf.features.models.tests;

import static io.restassured.RestAssured.*;
import static org.hamcrest.Matchers.*;
import static org.junit.Assert.*;
import org.junit.*;
import io.restassured.response.Response;
import io.restassured.path.json.JsonPath;

public class ApiIntegrationTest {

    private static final String BASE_URL = "http://localhost:8080";
    private String productName = "smartphone";
    private String featureName = "camera";
    private String configurationName = "basic";
    private String constraintId = "constraint-123";

    @BeforeClass
    public static void setupClass() {
        baseURI = BASE_URL;
    }

    @Before
    public void setupTestData() {
        // Create product
        Response response = given()
            .contentType("application/json")
            .body("{\"productName\": \"" + productName + "\"}")
            .when()
            .post("/products/" + productName);
        assumeTrue(response.getStatusCode() == 201);

        // Add feature to product
        response = given()
            .contentType("application/json")
            .body("{\"description\": \"High resolution camera\"}")
            .when()
            .post("/products/" + productName + "/features/" + featureName);
        assumeTrue(response.getStatusCode() == 201);

        // Create configuration
        response = given()
            .contentType("application/json")
            .when()
            .post("/products/" + productName + "/configurations/" + configurationName);
        assumeTrue(response.getStatusCode() == 201);

        // Create requires constraint
        response = given()
            .contentType("application/json")
            .body("{\"sourceFeature\": \"camera\", \"requiredFeature\": \"battery\"}")
            .when()
            .post("/products/" + productName + "/constraints/requires");
        assumeTrue(response.getStatusCode() == 201);

        // Create excludes constraint
        response = given()
            .contentType("application/json")
            .body("{\"sourceFeature\": \"camera\", \"excludedFeature\": \"lowBattery\"}")
            .when()
            .post("/products/" + productName + "/constraints/excludes");
        assumeTrue(response.getStatusCode() == 201);
    }

    @Test
    public void test_create_product_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"productName\": \"newProduct\"}")
            .when()
            .post("/products/newProduct");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_get_product_success() {
        Response response = given()
            .when()
            .get("/products/" + productName);
        assertEquals(200, response.getStatusCode());
    }

    @Test
    public void test_update_product_feature_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"description\": \"Updated camera feature\"}")
            .when()
            .put("/products/" + productName + "/features/" + featureName);
        assertEquals(200, response.getStatusCode());
    }

    @Test
    public void test_delete_product_feature_success() {
        Response response = given()
            .when()
            .delete("/products/" + productName + "/features/" + featureName);
        assertEquals(204, response.getStatusCode());
    }

    @Test
    public void test_get_all_products_success() {
        Response response = given()
            .when()
            .get("/products");
        assertEquals(200, response.getStatusCode());
    }

    @Test
    public void test_create_product_invalid_params() {
        Response response = given()
            .contentType("application/json")
            .body("{\"productName\": null}")
            .when()
            .post("/products/null");
        assertEquals(400, response.getStatusCode());
    }

    @Test
    public void test_get_product_not_found() {
        Response response = given()
            .when()
            .get("/products/nonexistent");
        assertEquals(404, response.getStatusCode());
    }

    @Test
    public void test_create_product_feature_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"description\": \"High resolution camera\"}")
            .when()
            .post("/products/" + productName + "/features/newFeature");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_get_product_features_success() {
        Response response = given()
            .when()
            .get("/products/" + productName + "/features");
        assertEquals(200, response.getStatusCode());
    }

    @Test
    public void test_create_configuration_success() {
        Response response = given()
            .contentType("application/json")
            .when()
            .post("/products/" + productName + "/configurations/newConfig");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_get_product_configurations_success() {
        Response response = given()
            .when()
            .get("/products/" + productName + "/configurations");
        assertEquals(200, response.getStatusCode());
    }

    @Test
    public void test_delete_product_success() {
        Response response = given()
            .when()
            .delete("/products/" + productName);
        assertEquals(204, response.getStatusCode());
    }

    @Test
    public void test_create_constraint_requires_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"sourceFeature\": \"camera\", \"requiredFeature\": \"battery\"}")
            .when()
            .post("/products/" + productName + "/constraints/requires");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_constraint_excludes_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"sourceFeature\": \"camera\", \"excludedFeature\": \"lowBattery\"}")
            .when()
            .post("/products/" + productName + "/constraints/excludes");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_delete_constraint_success() {
        Response response = given()
            .when()
            .delete("/products/" + productName + "/constraints/" + constraintId);
        assertEquals(204, response.getStatusCode());
    }
}