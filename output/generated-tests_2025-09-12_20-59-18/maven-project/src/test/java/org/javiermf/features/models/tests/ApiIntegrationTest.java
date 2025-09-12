package org.javiermf.features.models.tests;

import static io.restassured.RestAssured.*;
import static org.hamcrest.Matchers.*;
import static org.junit.Assert.*;
import org.junit.*;
import io.restassured.response.Response;
import io.restassured.path.json.JsonPath;

public class ApiIntegrationTest {

    private static final String BASE_URL = "http://localhost:8080";
    private String smartphoneProductName = "smartphone";
    private String cameraFeatureName = "camera";
    private String premiumConfigurationName = "premium";

    @BeforeClass
    public static void setupClass() {
        baseURI = BASE_URL;
    }

    @Before
    public void setupTestData() {
        // Create product 'smartphone'
        Response response = given()
            .when()
            .post("/products/" + smartphoneProductName);
        assertTrue(response.getStatusCode() == 201);

        // Create feature 'camera' for product 'smartphone'
        response = given()
            .when()
            .post("/products/" + smartphoneProductName + "/features/" + cameraFeatureName + "?description=High-resolution camera with optical zoom");
        assertTrue(response.getStatusCode() == 201);

        // Create configuration 'premium' for product 'smartphone'
        response = given()
            .when()
            .post("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName);
        assertTrue(response.getStatusCode() == 201);
    }

    @After
    public void tearDown() {
        // Delete configuration 'premium'
        given()
            .when()
            .delete("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName);

        // Delete feature 'camera'
        given()
            .when()
            .delete("/products/" + smartphoneProductName + "/features/" + cameraFeatureName);

        // Delete product 'smartphone'
        given()
            .when()
            .delete("/products/" + smartphoneProductName);
    }

    @Test
    public void test_get_products_success() {
        given()
            .when()
            .get("/products")
            .then()
            .statusCode(200)
            .body(notNullValue());
    }

    @Test
    public void test_create_product_success() {
        Response response = given()
            .when()
            .post("/products/" + smartphoneProductName);
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_product_invalid_params() {
        given()
            .when()
            .post("/products/")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_get_product_details_success() {
        given()
            .when()
            .get("/products/" + smartphoneProductName)
            .then()
            .statusCode(200)
            .body("productName", equalTo(smartphoneProductName));
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
            .delete("/products/" + smartphoneProductName)
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
            .get("/products/" + smartphoneProductName + "/features")
            .then()
            .statusCode(200)
            .body(notNullValue());
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
            .when()
            .post("/products/" + smartphoneProductName + "/features/" + cameraFeatureName + "?description=High-resolution camera with optical zoom");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_feature_invalid_params() {
        given()
            .when()
            .post("/products//features/")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_update_feature_success() {
        Response response = given()
            .when()
            .put("/products/" + smartphoneProductName + "/features/" + cameraFeatureName + "?description=Ultra high-resolution camera with 10x optical zoom");
        assertEquals(200, response.getStatusCode());
    }

    @Test
    public void test_update_feature_invalid_params() {
        given()
            .when()
            .put("/products//features/")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_delete_feature_success() {
        given()
            .when()
            .delete("/products/" + smartphoneProductName + "/features/" + cameraFeatureName)
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
            .get("/products/" + smartphoneProductName + "/configurations")
            .then()
            .statusCode(200)
            .body(notNullValue());
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
            .when()
            .post("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName);
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_configuration_invalid_params() {
        given()
            .when()
            .post("/products//configurations/")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_get_configuration_details_success() {
        given()
            .when()
            .get("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName)
            .then()
            .statusCode(200)
            .body("configurationName", equalTo(premiumConfigurationName));
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
            .delete("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName)
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
            .get("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName + "/features")
            .then()
            .statusCode(200)
            .body(notNullValue());
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
            .when()
            .post("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName + "/features/" + cameraFeatureName);
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_activate_feature_in_configuration_invalid_params() {
        given()
            .when()
            .post("/products//configurations//features/")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_deactivate_feature_in_configuration_success() {
        given()
            .when()
            .delete("/products/" + smartphoneProductName + "/configurations/" + premiumConfigurationName + "/features/" + cameraFeatureName)
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
            .when()
            .post("/products/" + smartphoneProductName + "/constraints/requires?sourceFeature=advanced-camera&requiredFeature=high-resolution-display");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_requires_constraint_invalid_params() {
        given()
            .when()
            .post("/products//constraints/requires")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_create_excludes_constraint_success() {
        Response response = given()
            .when()
            .post("/products/" + smartphoneProductName + "/constraints/excludes?sourceFeature=budget-processor&excludedFeature=gaming-gpu");
        assertEquals(201, response.getStatusCode());
    }

    @Test
    public void test_create_excludes_constraint_invalid_params() {
        given()
            .when()
            .post("/products//constraints/excludes")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_delete_constraint_success() {
        given()
            .when()
            .delete("/products/" + smartphoneProductName + "/constraints/123")
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