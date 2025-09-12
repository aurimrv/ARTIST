package org.javiermf.features.models.tests;

import static io.restassured.RestAssured.*;
import static org.hamcrest.Matchers.*;
import static org.junit.Assert.*;
import org.junit.*;
import io.restassured.response.Response;
import io.restassured.path.json.JsonPath;

public class ApiIntegrationTest {

    private static final String BASE_URL = "http://localhost:8080";
    private static String smartphoneId;
    private static String cameraFeatureId;
    private static String premiumConfigId;
    private static String constraintId;

    @Before
    public void setupTestData() {
        baseURI = BASE_URL;

        // Create product 'smartphone'
        Response response = given()
            .contentType("application/json")
            .body("{\"productName\": \"smartphone\"}")
            .when()
            .post("/products/smartphone");
        assertEquals(201, response.getStatusCode());
        smartphoneId = response.jsonPath().getString("id");

        // Create feature 'camera'
        response = given()
            .contentType("application/json")
            .body("{\"featureName\": \"camera\", \"description\": \"High-resolution camera with optical zoom\"}")
            .when()
            .post("/products/smartphone/features/camera");
        assertEquals(201, response.getStatusCode());
        cameraFeatureId = response.jsonPath().getString("id");

        // Create configuration 'premium'
        response = given()
            .contentType("application/json")
            .body("{\"configurationName\": \"premium\"}")
            .when()
            .post("/products/smartphone/configurations/premium");
        assertEquals(201, response.getStatusCode());
        premiumConfigId = response.jsonPath().getString("id");

        // Create constraint
        response = given()
            .contentType("application/json")
            .body("{\"sourceFeature\": \"advanced-camera\", \"requiredFeature\": \"high-resolution-display\"}")
            .when()
            .post("/products/smartphone/constraints/requires");
        assertEquals(201, response.getStatusCode());
        constraintId = response.jsonPath().getString("id");
    }

    @Test
    public void test_get_all_products_success() {
        given()
        .when()
            .get("/products")
        .then()
            .statusCode(200)
            .body("size()", greaterThan(0));
    }

    @Test
    public void test_create_product_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"productName\": \"smartphone\"}")
        .when()
            .post("/products/smartphone");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_product_invalid_params() {
        given()
            .contentType("application/json")
            .body("{\"productName\": null}")
        .when()
            .post("/products/")
        .then()
            .statusCode(400);
    }

    @Test
    public void test_get_product_details_success() {
        given()
        .when()
            .get("/products/smartphone")
        .then()
            .statusCode(200)
            .body("productName", equalTo("smartphone"));
    }

    @Test
    public void test_get_product_details_invalid_params() {
        given()
        .when()
            .get("/products/")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_delete_product_success() {
        given()
        .when()
            .delete("/products/smartphone")
        .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_product_invalid_params() {
        given()
        .when()
            .delete("/products/")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_get_product_features_success() {
        given()
        .when()
            .get("/products/smartphone/features")
        .then()
            .statusCode(200)
            .body("size()", greaterThan(0));
    }

    @Test
    public void test_get_product_features_invalid_params() {
        given()
        .when()
            .get("/products//features")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_create_feature_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"featureName\": \"camera\", \"description\": \"High-resolution camera with optical zoom\"}")
        .when()
            .post("/products/smartphone/features/camera");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_feature_invalid_params() {
        given()
            .contentType("application/json")
            .body("{\"featureName\": null, \"description\": null}")
        .when()
            .post("/products//features/")
        .then()
            .statusCode(400);
    }

    @Test
    public void test_update_feature_success() {
        given()
            .contentType("application/json")
            .body("{\"description\": \"Ultra high-resolution camera with 10x optical zoom\"}")
        .when()
            .put("/products/smartphone/features/camera")
        .then()
            .statusCode(200)
            .body("description", equalTo("Ultra high-resolution camera with 10x optical zoom"));
    }

    @Test
    public void test_update_feature_invalid_params() {
        given()
            .contentType("application/json")
            .body("{\"description\": null}")
        .when()
            .put("/products//features/")
        .then()
            .statusCode(400);
    }

    @Test
    public void test_delete_feature_success() {
        given()
        .when()
            .delete("/products/smartphone/features/camera")
        .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_feature_invalid_params() {
        given()
        .when()
            .delete("/products//features/")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_get_product_configurations_success() {
        given()
        .when()
            .get("/products/smartphone/configurations")
        .then()
            .statusCode(200)
            .body("size()", greaterThan(0));
    }

    @Test
    public void test_get_product_configurations_invalid_params() {
        given()
        .when()
            .get("/products//configurations")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_create_configuration_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"configurationName\": \"premium\"}")
        .when()
            .post("/products/smartphone/configurations/premium");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_configuration_invalid_params() {
        given()
            .contentType("application/json")
            .body("{\"configurationName\": null}")
        .when()
            .post("/products//configurations/")
        .then()
            .statusCode(400);
    }

    @Test
    public void test_get_configuration_details_success() {
        given()
        .when()
            .get("/products/smartphone/configurations/premium")
        .then()
            .statusCode(200)
            .body("configurationName", equalTo("premium"));
    }

    @Test
    public void test_get_configuration_details_invalid_params() {
        given()
        .when()
            .get("/products//configurations/")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_delete_configuration_success() {
        given()
        .when()
            .delete("/products/smartphone/configurations/premium")
        .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_configuration_invalid_params() {
        given()
        .when()
            .delete("/products//configurations/")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_get_configuration_features_success() {
        given()
        .when()
            .get("/products/smartphone/configurations/premium/features")
        .then()
            .statusCode(200)
            .body("size()", greaterThan(0));
    }

    @Test
    public void test_get_configuration_features_invalid_params() {
        given()
        .when()
            .get("/products//configurations//features")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_activate_feature_in_configuration_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"featureName\": \"camera\"}")
        .when()
            .post("/products/smartphone/configurations/premium/features/camera");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_activate_feature_in_configuration_invalid_params() {
        given()
            .contentType("application/json")
            .body("{\"featureName\": null}")
        .when()
            .post("/products//configurations//features/")
        .then()
            .statusCode(400);
    }

    @Test
    public void test_deactivate_feature_in_configuration_success() {
        given()
        .when()
            .delete("/products/smartphone/configurations/premium/features/camera")
        .then()
            .statusCode(204);
    }

    @Test
    public void test_deactivate_feature_in_configuration_invalid_params() {
        given()
        .when()
            .delete("/products//configurations//features/")
        .then()
            .statusCode(404);
    }

    @Test
    public void test_create_requires_constraint_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"sourceFeature\": \"advanced-camera\", \"requiredFeature\": \"high-resolution-display\"}")
        .when()
            .post("/products/smartphone/constraints/requires");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_requires_constraint_invalid_params() {
        given()
            .contentType("application/json")
            .body("{\"sourceFeature\": null, \"requiredFeature\": null}")
        .when()
            .post("/products//constraints/requires")
        .then()
            .statusCode(400);
    }

    @Test
    public void test_create_excludes_constraint_success() {
        Response response = given()
            .contentType("application/json")
            .body("{\"sourceFeature\": \"budget-processor\", \"excludedFeature\": \"gaming-gpu\"}")
        .when()
            .post("/products/smartphone/constraints/excludes");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_excludes_constraint_invalid_params() {
        given()
            .contentType("application/json")
            .body("{\"sourceFeature\": null, \"excludedFeature\": null}")
        .when()
            .post("/products//constraints/excludes")
        .then()
            .statusCode(400);
    }

    @Test
    public void test_delete_constraint_success() {
        given()
        .when()
            .delete("/products/smartphone/constraints/123")
        .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_constraint_invalid_params() {
        given()
        .when()
            .delete("/products//constraints/")
        .then()
            .statusCode(404);
    }
}