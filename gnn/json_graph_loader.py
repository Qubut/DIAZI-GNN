import json
from loguru import logger
from neo4j import AsyncGraphDatabase
from returns.trampolines import trampoline, Trampoline
from returns.future import future_safe
from gnn.utils import json_parsing_pipeline
from pathlib import Path
import asyncio
import os
import asyncstdlib as a
from collections import deque
from typing import Any


class AsyncJSONToNeo4j:
    def __init__(self, database: str, gds_graph_name="jsonGraph"):
        """
        Initialize the Async Neo4j driver and configuration.
        """
        self.driver = None
        self.session = None
        self.database = database
        self.gds_graph_name = gds_graph_name
    async def __aenter__(self):
        """
        Setup the Neo4j driver and session.
        """
        logger.info("Establishing connection to Neo4j")
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = AsyncGraphDatabase.driver(
            uri=uri, auth=(user, password), database=self.database
        )
        self.session = self.driver.session()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """
        Tear down the Neo4j session and driver.
        """
        if self.session:
            await self.session.close()
            logger.info("Neo4j session closed")
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j driver closed")

    @future_safe
    async def create_node(self, label, properties):
        """
        Create a node in Neo4j with a dynamic label and properties.
        """
        props = ", ".join(f"{key}: ${key}" for key in properties.keys())
        query = f"MERGE (n:{label} {{{props}}})"
        logger.debug(f"Creating node with label: {label}, properties: {properties}")
        return await self.session.write_transaction(
            lambda tx: tx.run(query, **properties)
        )

    @future_safe
    async def create_relationship(
        self, from_label, from_properties, to_label, to_properties, rel_type
    ):
        """
        Create a relationship between two nodes in Neo4j.
        """
        from_props = ", ".join(f"{key}: ${key}_from" for key in from_properties.keys())
        to_props = ", ".join(f"{key}: ${key}_to" for key in to_properties.keys())
        query = f"""
        MATCH (a:{from_label} {{{from_props}}})
        MATCH (b:{to_label} {{{to_props}}})
        MERGE (a)-[:{rel_type}]->(b)
        """
        params = {f"{key}_from": value for key, value in from_properties.items()}
        params.update({f"{key}_to": value for key, value in to_properties.items()})
        logger.debug(f"Creating relationship: {from_label} -> {to_label} [{rel_type}]")
        return await self.session.write_transaction(lambda tx: tx.run(query, **params))

    @future_safe
    async def process_json(self, data: dict[str, Any]):
        """
        Processes JSON data iteratively to create nodes and relationships in Neo4j.

        This method uses a stack-based approach to traverse the JSON object.
        The primary aim is to represent the hierarchical structure of the JSON in
        the Neo4j graph database. Primitive values (strings, numbers, booleans)
        are stored as properties of their parent nodes instead of being created as
        separate nodes.

        The process follows these steps:
        1. For dictionary keys, a new node is created in Neo4j, with the key being
        represented as the node label. If the corresponding value is a primitive
        (e.g., string, number, boolean), it is added as a property to the node.
        If the value is a nested object or array, it is pushed onto the stack for
        further processing.

        2. For lists, each item in the list is added as a new node connected directly
        to the parent node with a "HAS" relationship. Each item is treated as its
        own subgraph, allowing for complex structures within list items.

        3. For primitive values directly under a dictionary key, the value is stored
        as a property on the parent node, and no additional relationships are
        created.

        4. A root node is created to serve as the starting point of the graph,
        ensuring that even top-level nodes have a parent.

        Parameters:
            data (dict[str, Any]): The JSON data to process, represented as a Python
            dictionary. Nested objects and arrays are fully supported.

        Returns:
            None: This function modifies the Neo4j graph directly through `create_node`
            and `create_relationship` asynchronous calls.

        Raises:
            Any exceptions related to database connectivity or invalid data will propagate
            and should be handled by the caller.
        """
        from collections import deque

        stack = deque()
        # Initialize with a root node
        root_label = "Root"
        root_properties = {"name": "root"}
        stack.append((root_label, root_properties, None, data))

        is_dict = lambda val: isinstance(val, dict)
        is_list = lambda val: isinstance(val, list)
        is_primitive = lambda val: not (is_dict(val) or is_list(val))

        # Create the root node
        await self.create_node(root_label, root_properties)

        while stack:
            parent_label, parent_properties, rel_type, current_data = stack.pop()

            if is_dict(current_data):
                for key, value in current_data.items():
                    node_label = key.capitalize()
                    node_properties = {"name": key}

                    if is_primitive(value):
                        node_properties["value"] = value
                        await self.create_node(node_label, node_properties)
                        await self.create_relationship(
                            parent_label,
                            parent_properties,
                            node_label,
                            node_properties,
                            rel_type or "HAS",
                        )
                    else:
                        # Create node and relationship before processing children
                        await self.create_node(node_label, node_properties)
                        await self.create_relationship(
                            parent_label,
                            parent_properties,
                            node_label,
                            node_properties,
                            rel_type or "HAS",
                        )
                        stack.append((node_label, node_properties, "HAS", value))

            elif is_list(current_data):
                for idx, item in enumerate(current_data):
                    # Create a node for each list item
                    node_label = f"{parent_label}Item"
                    node_properties = {"index": idx}

                    if is_primitive(item):
                        node_properties["value"] = item
                        await self.create_node(node_label, node_properties)
                        await self.create_relationship(
                            parent_label,
                            parent_properties,
                            node_label,
                            node_properties,
                            "HAS",
                        )
                    else:
                        # Create node and relationship before processing children
                        await self.create_node(node_label, node_properties)
                        await self.create_relationship(
                            parent_label,
                            parent_properties,
                            node_label,
                            node_properties,
                            "HAS",
                        )
                        stack.append((node_label, node_properties, "HAS", item))

            else:
                # Handle primitive values that are not under a dictionary key
                if parent_label:
                    parent_properties["value"] = current_data
                    await self.create_node(parent_label, parent_properties)


    @future_safe
    async def project_graph_in_gds(self):
        """
        Project all nodes and 'HAS' relationships into an in-memory graph
        named self.gds_graph_name in the GDS catalog.
        """
        drop_query = f"""
        CALL gds.graph.drop('{self.gds_graph_name}', false)
        YIELD graphName
        """
        try:
            await self.session.run(drop_query)
            logger.info(f"Dropped existing '{self.gds_graph_name}' from GDS.")
        except:
            logger.info(f"'{self.gds_graph_name}' did not exist or could not be dropped.")

        project_query = f"""
        CALL gds.graph.project(
          '{self.gds_graph_name}',
          '*',     // project all labels
          {{
            relationships: {{
              type: 'HAS',
              orientation: 'UNDIRECTED'
            }}
          }}
        )
        """
        logger.info(f"Projecting '{self.gds_graph_name}' in GDS...")
        await self.session.run(project_query)
        logger.info(f"'{self.gds_graph_name}' was successfully projected in GDS.")

    @future_safe
    async def estimate_leiden(self, write_property: str = "communityId"):
        """
        Estimate memory usage for running Leiden in write mode on `self.gds_graph_name`.
        """
        query = f"""
        CALL gds.leiden.write.estimate('{self.gds_graph_name}', {{
          writeProperty: '{write_property}',
          randomSeed: 19
        }})
        YIELD nodeCount, relationshipCount, requiredMemory
        RETURN nodeCount, relationshipCount, requiredMemory
        """
        logger.info(f"Estimating memory for Leiden on '{self.gds_graph_name}'...")
        result_cursor = await self.session.run(query)
        record = await result_cursor.single()

        logger.info(
            "Memory Estimation -> "
            f"nodeCount: {record['nodeCount']}, "
            f"relationshipCount: {record['relationshipCount']}, "
            f"requiredMemory: {record['requiredMemory']}"
        )
        return record

    @future_safe
    async def run_leiden_write(
        self,
        write_property: str = "communityId",
        concurrency: int = 4,
        relationship_weight_property: str = None,
        include_intermediate: bool = False,
    ):
        """
        Runs Leiden in write mode on `self.gds_graph_name`,
        writing the community IDs (or intermediateCommunities) back to Neo4j.
        """
        # Build optional configurations:
        #   - relationshipWeightProperty
        #   - includeIntermediateCommunities
        #   - concurrency
        #   - randomSeed, etc.
        config = f"""
          writeProperty: '{write_property}',
          randomSeed: 19,
          concurrency: {concurrency},
          includeIntermediateCommunities: {str(include_intermediate).lower()}
        """
        if relationship_weight_property:
            config += f", relationshipWeightProperty: '{relationship_weight_property}'"

        query = f"""
        CALL gds.leiden.write('{self.gds_graph_name}', {{
            {config}
        }})
        YIELD communityCount, modularity, nodePropertiesWritten
        RETURN communityCount, modularity, nodePropertiesWritten
        """
        logger.info(f"Running Leiden (write mode) on '{self.gds_graph_name}'...")
        result_cursor = await self.session.run(query)
        result = await result_cursor.single()

        logger.info(
            f"Leiden results for '{self.gds_graph_name}' -> "
            f"communityCount: {result['communityCount']}, "
            f"modularity: {result['modularity']:.4f}, "
            f"nodePropertiesWritten: {result['nodePropertiesWritten']}"
        )
        return result

async def process_file(file_path: Path, processor):
    """
    Process a single JSON file: read, parse, and process the JSON data.
    """
    logger.info(f"Processing file: {file_path}")
    result = await json_parsing_pipeline(file_path).bind_awaitable(processor)
    return result


async def process_directory(data_directory: Path, processor: AsyncJSONToNeo4j):
    """
    Process all JSON files in the specified data directory concurrently.
    """
    logger.info(f"Processing directory: {data_directory}")
    json_files = list(data_directory.glob("*.json"))
    tasks = [process_file(file_path, processor) for file_path in json_files]
    results = await asyncio.gather(*tasks)
    return results
