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
    private String configurationName = "premium";

    @BeforeClass
    public static void setupClass() {
        baseURI = BASE_URL;
    }

    @Before
    public void setupTestData() {
        // Create product
        Response response = given().post("/products/" + productName);
        assumeTrue(response.getStatusCode() == 201);

        // Create feature
        response = given().post("/products/" + productName + "/features/" + featureName);
        assumeTrue(response.getStatusCode() == 201);

        // Create configuration
        response = given().post("/products/" + productName + "/configurations/" + configurationName);
        assumeTrue(response.getStatusCode() == 201);
    }

    @After
    public void teardownTestData() {
        // Delete feature
        given().delete("/products/" + productName + "/features/" + featureName);

        // Delete configuration
        given().delete("/products/" + productName + "/configurations/" + configurationName);

        // Delete product
        given().delete("/products/" + productName);
    }

    @Test
    public void test_get_products_success() {
        given().when().get("/products")
                .then().statusCode(200)
                .body(notNullValue());
    }

    @Test
    public void test_create_product_success() {
        String newProductName = "tablet";
        Response response = given().post("/products/" + newProductName);
        assertEquals(201, response.getStatusCode());
        given().delete("/products/" + newProductName);
    }

    @Test
    public void test_create_product_invalid_params() {
        given().post("/products/")
                .then().statusCode(400);
    }

    @Test
    public void test_get_product_details_success() {
        given().when().get("/products/" + productName)
                .then().statusCode(200)
                .body("productName", equalTo(productName));
    }

    @Test
    public void test_get_product_details_invalid_params() {
        given().get("/products/")
                .then().statusCode(404);
    }

    @Test
    public void test_delete_product_success() {
        String newProductName = "laptop";
        given().post("/products/" + newProductName);
        given().delete("/products/" + newProductName)
                .then().statusCode(204);
    }

    @Test
    public void test_delete_product_invalid_params() {
        given().delete("/products/")
                .then().statusCode(404);
    }

    @Test
    public void test_get_product_features_success() {
        given().when().get("/products/" + productName + "/features")
                .then().statusCode(200)
                .body(notNullValue());
    }

    @Test
    public void test_get_product_features_invalid_params() {
        given().get("/products//features")
                .then().statusCode(404);
    }

    @Test
    public void test_create_feature_success() {
        String newFeatureName = "battery";
        Response response = given().post("/products/" + productName + "/features/" + newFeatureName);
        assertEquals(201, response.getStatusCode());
        given().delete("/products/" + productName + "/features/" + newFeatureName);
    }

    @Test
    public void test_create_feature_invalid_params() {
        given().post("/products//features/")
                .then().statusCode(400);
    }

    @Test
    public void test_update_feature_success() {
        given().put("/products/" + productName + "/features/" + featureName)
                .then().statusCode(200);
    }

    @Test
    public void test_update_feature_invalid_params() {
        given().put("/products//features/")
                .then().statusCode(400);
    }

    @Test
    public void test_delete_feature_success() {
        String newFeatureName = "gps";
        given().post("/products/" + productName + "/features/" + newFeatureName);
        given().delete("/products/" + productName + "/features/" + newFeatureName)
                .then().statusCode(204);
    }

    @Test
    public void test_delete_feature_invalid_params() {
        given().delete("/products//features/")
                .then().statusCode(404);
    }

    @Test
    public void test_get_product_configurations_success() {
        given().when().get("/products/" + productName + "/configurations")
                .then().statusCode(200)
                .body(notNullValue());
    }

    @Test
    public void test_get_product_configurations_invalid_params() {
        given().get("/products//configurations")
                .then().statusCode(404);
    }

    @Test
    public void test_create_configuration_success() {
        String newConfigurationName = "basic";
        Response response = given().post("/products/" + productName + "/configurations/" + newConfigurationName);
        assertEquals(201, response.getStatusCode());
        given().delete("/products/" + productName + "/configurations/" + newConfigurationName);
    }

    @Test
    public void test_create_configuration_invalid_params() {
        given().post("/products//configurations/")
                .then().statusCode(400);
    }

    @Test
    public void test_get_configuration_details_success() {
        given().when().get("/products/" + productName + "/configurations/" + configurationName)
                .then().statusCode(200)
                .body("configurationName", equalTo(configurationName));
    }

    @Test
    public void test_get_configuration_details_invalid_params() {
        given().get("/products//configurations/")
                .then().statusCode(404);
    }

    @Test
    public void test_delete_configuration_success() {
        String newConfigurationName = "standard";
        given().post("/products/" + productName + "/configurations/" + newConfigurationName);
        given().delete("/products/" + productName + "/configurations/" + newConfigurationName)
                .then().statusCode(204);
    }

    @Test
    public void test_delete_configuration_invalid_params() {
        given().delete("/products//configurations/")
                .then().statusCode(404);
    }

    @Test
    public void test_get_configuration_features_success() {
        given().when().get("/products/" + productName + "/configurations/" + configurationName + "/features")
                .then().statusCode(200)
                .body(notNullValue());
    }

    @Test
    public void test_get_configuration_features_invalid_params() {
        given().get("/products//configurations//features")
                .then().statusCode(404);
    }

    @Test
    public void test_activate_feature_in_configuration_success() {
        String newFeatureName = "wifi";
        given().post("/products/" + productName + "/features/" + newFeatureName);
        Response response = given().post("/products/" + productName + "/configurations/" + configurationName + "/features/" + newFeatureName);
        assertEquals(201, response.getStatusCode());
        given().delete("/products/" + productName + "/features/" + newFeatureName);
    }

    @Test
    public void test_activate_feature_in_configuration_invalid_params() {
        given().post("/products//configurations//features/")
                .then().statusCode(400);
    }

    @Test
    public void test_deactivate_feature_in_configuration_success() {
        String newFeatureName = "bluetooth";
        given().post("/products/" + productName + "/features/" + newFeatureName);
        given().post("/products/" + productName + "/configurations/" + configurationName + "/features/" + newFeatureName);
        given().delete("/products/" + productName + "/configurations/" + configurationName + "/features/" + newFeatureName)
                .then().statusCode(204);
        given().delete("/products/" + productName + "/features/" + newFeatureName);
    }

    @Test
    public void test_deactivate_feature_in_configuration_invalid_params() {
        given().delete("/products//configurations//features/")
                .then().statusCode(404);
    }

    @Test
    public void test_create_requires_constraint_success() {
        String sourceFeature = "advanced-camera";
        String requiredFeature = "high-resolution-display";
        given().post("/products/" + productName + "/features/" + sourceFeature);
        given().post("/products/" + productName + "/features/" + requiredFeature);
        Response response = given().post("/products/" + productName + "/constraints/requires")
                .param("sourceFeature", sourceFeature)
                .param("requiredFeature", requiredFeature);
        assertEquals(201, response.getStatusCode());
        given().delete("/products/" + productName + "/features/" + sourceFeature);
        given().delete("/products/" + productName + "/features/" + requiredFeature);
    }

    @Test
    public void test_create_requires_constraint_invalid_params() {
        given().post("/products//constraints/requires")
                .then().statusCode(400);
    }

    @Test
    public void test_create_excludes_constraint_success() {
        String sourceFeature = "budget-processor";
        String excludedFeature = "gaming-gpu";
        given().post("/products/" + productName + "/features/" + sourceFeature);
        given().post("/products/" + productName + "/features/" + excludedFeature);
        Response response = given().post("/products/" + productName + "/constraints/excludes")
                .param("sourceFeature", sourceFeature)
                .param("excludedFeature", excludedFeature);
        assertEquals(201, response.getStatusCode());
        given().delete("/products/" + productName + "/features/" + sourceFeature);
        given().delete("/products/" + productName + "/features/" + excludedFeature);
    }

    @Test
    public void test_create_excludes_constraint_invalid_params() {
        given().post("/products//constraints/excludes")
                .then().statusCode(400);
    }

    @Test
    public void test_delete_constraint_success() {
        int constraintId = 123;
        given().delete("/products/" + productName + "/constraints/" + constraintId)
                .then().statusCode(204);
    }

    @Test
    public void test_delete_constraint_invalid_params() {
        given().delete("/products//constraints/")
                .then().statusCode(404);
    }
}